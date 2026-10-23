// Adapter: the rewritten variable server behind Trick::VariableServer (rewrite Phase 5).
// See include/trick/vs/adapter/Server.hh.

#include "trick/vs/adapter/Server.hh"

#include "trick/ExecutiveException.hh"
#include "trick/JobData.hh"
#include "trick/Message_proto.hh"
#include "trick/VariableServer.hh"
#include "trick/command_line_protos.h"
#include "trick/exec_proto.h"
#include "trick/input_processor_proto.h"
#include "trick/map_trick_units_to_udunits.hh"
#include "trick/memorymanager_c_intf.h"
#include "trick/message_proto.h"
#include "trick/message_type.h"
#include "trick/realtimesync_proto.h"
#include "trick/sie_c_intf.h"
#include "trick/vs/CLocale.hh"
#include "trick/vs/Endpoint.hh"

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <pthread.h>
#include <pwd.h>
#include <sched.h>
#include <unistd.h>

namespace Trick
{
    namespace vs
    {
        namespace adapter
        {

            namespace
            {
                Server* g_active = nullptr;
                thread_local Session* t_current = nullptr;
                /** How many memory locks this thread holds (a Python line, then the copies it asks for). */
                thread_local int t_memory_held = 0;

                /** Counts a memory lock this thread holds, for its scope (exceptions included). */
                struct MemoryHeld
                {
                        MemoryHeld() noexcept { ++t_memory_held; }
                        ~MemoryHeld() { --t_memory_held; }
                        MemoryHeld(const MemoryHeld&)            = delete;
                        MemoryHeld& operator=(const MemoryHeld&) = delete;
                };

                std::string with_newline(std::string text)
                {
                    if (text.empty() || text.back() != '\n')
                        text += '\n';
                    return text;
                }

                void set_thread_name(const std::string& name)
                {
#if defined(__linux__)
                    pthread_setname_np(pthread_self(), name.substr(0, 15).c_str());
#elif defined(__APPLE__)
                    pthread_setname_np(name.substr(0, 15).c_str());
#else
                    (void)name;
#endif
                }
            } // namespace

            // --------------------------------------------------------------
            // Clocks
            // --------------------------------------------------------------

            long long ExecClock::time_tics() const { return exec_get_time_tics(); }
            long long ExecClock::tic_value() const { return exec_get_time_tic_value(); }
            long long ExecClock::frame_count() const { return exec_get_frame_count(); }
            long long ExecClock::freeze_time_tics() const { return exec_get_freeze_time_tics(); }
            long long ExecClock::freeze_frame_count() const { return exec_get_freeze_frame_count(); }
            bool ExecClock::real_time() const { return is_real_time() != 0; }
            int ExecClock::exec_mode() const { return static_cast<int>(exec_get_mode()); }

            void MirrorClock::update(const Clock& from) noexcept
            {
                _time.store(from.time_tics(), std::memory_order_relaxed);
                _tic_value.store(from.tic_value(), std::memory_order_relaxed);
                _frame.store(from.frame_count(), std::memory_order_relaxed);
                _freeze_time.store(from.freeze_time_tics(), std::memory_order_relaxed);
                _freeze_frame.store(from.freeze_frame_count(), std::memory_order_relaxed);
                _real_time.store(from.real_time(), std::memory_order_relaxed);
                _mode.store(from.exec_mode(), std::memory_order_relaxed);
            }

            // --------------------------------------------------------------
            // var_set
            // --------------------------------------------------------------

            int assign_variable(const char* name, const cmd::SetValue& value, const char* units)
            {
                RefPtr ref = resolve_ref(name);
                if (!ref)
                {
                    message_publish(MSG_WARNING, "reference attributes not found for variable %s in call to var_set\n",
                                    name);
                    return 2;
                }
                if (ref->attr == nullptr || (ref->attr->io & TRICK_VAR_INPUT) == 0)
                {
                    message_publish(MSG_WARNING, "Cannot assign to %s because io_spec does not allow input\n", name);
                    return 1;
                }
                V_TREE v_tree {};
                V_DATA v_data {};
                v_tree.v_data = &v_data;
                std::string text; // keeps a string value alive through ref_assignment
                if (const double* d = std::get_if<double>(&value))
                {
                    v_data.type    = TRICK_DOUBLE;
                    v_data.value.d = *d;
                }
                else if (const long long* ll = std::get_if<long long>(&value))
                {
                    v_data.type     = TRICK_LONG_LONG;
                    v_data.value.ll = *ll;
                }
                else if (const std::string* s = std::get_if<std::string>(&value))
                {
                    text             = *s;
                    v_data.type      = TRICK_STRING;
                    v_data.value.cp  = &text[0];
                }
                else
                {
                    v_data.type     = TRICK_VOID_PTR;
                    v_data.value.vp = nullptr;
                }
                if (ref->units != nullptr)
                {
                    std::free(ref->units);
                    ref->units = nullptr;
                }
                if (units != nullptr)
                    ref->units = strdup(map_trick_units_to_udunits(units).c_str());
                ref_assignment(ref.get(), &v_tree);
                return 0;
            }

            // --------------------------------------------------------------
            // Server
            // --------------------------------------------------------------

            Server* Server::active() noexcept { return g_active; }

            Session* Server::current_session() noexcept { return t_current; }

            Server::Server(VariableServer& vs)
                : _vs(vs)
            {
                g_active = this;
            }

            Server::~Server()
            {
                if (g_active == this)
                    g_active = nullptr;
                _stopping.store(true);
                stop_listener();
            }

            void Server::config_changed()
            {
                _enabled.store(_vs.get_enabled());
                _allow.store(_vs.get_allow_connections());
                _bypass.store(_vs.get_bypass_ip_check());
                _info_msg.store(_vs.get_info_msg());
                const bool log         = _vs.get_log();
                const bool session_log = _vs.get_session_log();
                const bool log_changed = _log.exchange(log) != log;
                const bool sess_changed = _session_log.exchange(session_log) != session_log;
                if (log_changed || sess_changed)
                {
                    // set_var_server_log_on and friends apply to every session, as in the old server.
                    const auto sessions = _registry.sessions(); // keep the vector alive for the loop
                    for (const auto& s : *sessions)
                    {
                        if (log_changed)
                            s->set_server_log(log);
                        if (sess_changed)
                            s->set_server_session_log(session_log);
                    }
                }
                std::vector<std::string> errors;
                AddressFilter filter = AddressFilter::from(_vs.get_ip_allowlist(), &errors);
                for (const std::string& e : errors)
                    message_publish(MSG_WARNING, "Trick VariableServer: allowlist entry ignored: %s\n", e.c_str());
                std::lock_guard<std::mutex> guard(_filter_mutex);
                _filter   = std::move(filter);
                _user_tag = _vs.get_listen_thread().get_user_tag();
            }

            // Listener -------------------------------------------------------

            Expected<Listener> Server::open_main_listener()
            {
                VariableServerListenThread& lt = _vs.get_listen_thread();
                if (lt.get_user_requested_address())
                    return Listener::open(system_interface(), lt.get_source_address(), lt.get_port());
                return Listener::open(system_interface(), "", 0);
            }

            Expected<void> Server::start_listener()
            {
                std::optional<Beacon> beacon;
                if (_vs.get_listen_thread().get_broadcast())
                {
                    auto b = Beacon::open();
                    if (b)
                        beacon = std::move(b.value());
                    else
                        message_publish(MSG_WARNING, "Trick VariableServer: no beacon: %s\n",
                                        b.error().message.c_str());
                }
                auto loop = ListenLoop::create(*this, std::move(beacon));
                if (!loop)
                    return loop.error();
                _loop = std::move(loop.value());
                if (_main_listener)
                    _loop->add(std::move(*_main_listener));
                _main_listener.reset();
                for (Listener& l : _extra_listeners)
                    _loop->add(std::move(l));
                _extra_listeners.clear();
                _listen_thread = std::thread([this] {
                    ScopedCLocale c_locale;
                    set_thread_name("VarServListen");
                    apply_affinity();
                    _loop->run();
                });
                return {};
            }

            void Server::stop_listener()
            {
                if (!_loop)
                    return;
                {
                    // The listener may be waiting in accepting() for a reload to end.
                    std::lock_guard<std::mutex> guard(_resume_mutex);
                    _listener_stopping.store(true);
                }
                _resume_cv.notify_all();
                _loop->stop();
                if (_listen_thread.joinable())
                    _listen_thread.join();
                _listener_stopping.store(false);
                std::vector<Listener> listeners = _loop->take_listeners();
                _loop.reset();
                bool first = true;
                for (Listener& l : listeners)
                {
                    if (first && _initialized)
                        _main_listener = std::move(l);
                    else
                        _extra_listeners.push_back(std::move(l));
                    first = false;
                }
            }

            void Server::apply_affinity()
            {
#if defined(__linux__)
                // ThreadBase allocates the set with CPU_ALLOC for the CPUs online.
                cpu_set_t* cpus      = _vs.get_listen_thread().get_cpus();
                const long cpu_count = sysconf(_SC_NPROCESSORS_ONLN);
                if (cpus == nullptr || cpu_count <= 0)
                    return;
                const std::size_t size = CPU_ALLOC_SIZE(cpu_count);
                if (CPU_COUNT_S(size, cpus) > 0)
                    pthread_setaffinity_np(pthread_self(), size, cpus);
#endif
            }

            int Server::default_data()
            {
                _mirror_clock.update(_exec_clock);
                std::lock_guard<std::recursive_mutex> guard(_listen_mutex);
                // Bind now, so the port is known when initialization starts (external applications).
                auto l = Listener::open(system_interface(), "", 0);
                if (!l)
                {
                    message_publish(MSG_ERROR, "Trick VariableServer: could not open the listen socket: %s\n",
                                    l.error().message.c_str());
                    return -1;
                }
                _vs.get_listen_thread().set_bound_address(l.value().hostname(), l.value().port());
                _main_listener = std::move(l.value());
                return 0;
            }

            int Server::init()
            {
                std::lock_guard<std::recursive_mutex> guard(_listen_mutex);
                if (_initialized)
                    return 0; // init and monte_master_init both call this
                _mirror_clock.update(_exec_clock);
                config_changed();

                // The beacon fields that do not change.
                std::string version = exec_get_current_version();
                version.erase(version.find_last_not_of(" \t\f\v\n\r") + 1);
                const passwd* pw         = getpwuid(getuid());
                _beacon_base.user        = pw != nullptr ? pw->pw_name : "unknown";
                _beacon_base.pid         = static_cast<long>(getpid());
                _beacon_base.sim_dir     = command_line_args_get_default_dir();
                _beacon_base.executable  = command_line_args_get_cmdline_name();
                _beacon_base.input_file  = command_line_args_get_input_file();
                _beacon_base.version     = version;

                VariableServerListenThread& lt = _vs.get_listen_thread();
                if (!_vs.get_enabled() && !lt.get_broadcast())
                    return 0;
                if (lt.get_user_requested_address() || !_main_listener)
                {
                    _main_listener.reset();
                    auto l = open_main_listener();
                    if (!l)
                    {
                        message_publish(MSG_ERROR,
                                        "ERROR: Could not establish variable server source_address %s: port %d. "
                                        "Aborting.\n",
                                        lt.get_source_address().c_str(), lt.get_port());
                        return -1;
                    }
                    _main_listener = std::move(l.value());
                }
                lt.set_bound_address(_main_listener->hostname(), _main_listener->port());
                _initialized = true;
                auto started = start_listener();
                if (!started)
                {
                    message_publish(MSG_ERROR, "Trick VariableServer: %s\n", started.error().message.c_str());
                    return -1;
                }
                return 0;
            }

            int Server::restart()
            {
                std::lock_guard<std::recursive_mutex> guard(_listen_mutex);
                config_changed();
                VariableServerListenThread& lt = _vs.get_listen_thread();
                if (!_initialized)
                    return 0;
                stop_listener();
                if (lt.get_user_requested_address()
                    && (!_main_listener || _main_listener->port() != lt.get_port() || lt.get_port() == 0))
                {
                    message_publish(MSG_INFO, "variable server restart user_port requested set %s:%d\n",
                                    lt.get_source_address().c_str(), lt.get_port());
                    _main_listener.reset();
                    auto l = open_main_listener();
                    if (!l)
                    {
                        message_publish(MSG_ERROR, "ERROR: Could not establish listen port %d for Variable Server. "
                                                   "Aborting.\n",
                                        lt.get_port());
                        return -1;
                    }
                    _main_listener = std::move(l.value());
                }
                if (_main_listener)
                {
                    lt.set_bound_address(_main_listener->hostname(), _main_listener->port());
                    message_publish(MSG_INFO, "restart variable server message port = %d\n", _main_listener->port());
                }
                auto started = start_listener();
                return started ? 0 : -1;
            }

            int Server::create_tcp_socket(const char* address, unsigned short port)
            {
                const std::string requested = address != nullptr ? address : "";
                auto l                      = Listener::open(system_interface(), requested, port);
                if (!l)
                {
                    message_publish(MSG_ERROR,
                                    "ERROR: Could not establish additional listen port at address %s and port %d for "
                                    "Variable Server.\n",
                                    requested.c_str(), port);
                    return -1;
                }
                message_publish(MSG_INFO, "Created TCP variable server %s: %d\n", l.value().hostname().c_str(),
                                l.value().port());
                std::lock_guard<std::recursive_mutex> guard(_listen_mutex);
                const bool running = _loop != nullptr;
                stop_listener();
                _extra_listeners.push_back(std::move(l.value()));
                if (running)
                    start_listener();
                return 0;
            }

            int Server::create_udp_socket(const char* address, unsigned short port)
            {
                const std::string requested = address != nullptr ? address : "";
                auto c                      = UdpConnection::open(system_interface(), requested, port);
                if (!c)
                {
                    message_publish(MSG_ERROR,
                                    "ERROR: Could not establish UDP port at address %s and port %d for Variable "
                                    "Server.\n",
                                    requested.c_str(), port);
                    return -1;
                }
                message_publish(MSG_INFO, "Created UDP variable server %s: %d\n", requested.c_str(),
                                c.value()->local().port());
                c.value()->set_sender_filter([this](const Address& sender) { return accepting() && allowed(sender); });
                start_runner(std::move(c.value()), std::string(), 0);
                return 0;
            }

            int Server::create_multicast_socket(const char* group, const char* address, unsigned short port)
            {
                if (group == nullptr || group[0] == '\0')
                {
                    message_publish(MSG_ERROR, "Multicast address must be defined.\n");
                    return -1;
                }
                const std::string requested = address != nullptr ? address : "";
                auto c = MulticastConnection::open(system_interface(), group, requested, port);
                if (!c)
                {
                    message_publish(MSG_ERROR,
                                    "ERROR: Could not establish Multicast port at address %s and port %d for Variable "
                                    "Server.\n",
                                    requested.c_str(), port);
                    return -1;
                }
                message_publish(MSG_INFO, "Multicast variable server output %s:%d\n", group,
                                c.value()->local().port());
                c.value()->set_sender_filter([this](const Address& sender) { return accepting() && allowed(sender); });
                start_runner(std::move(c.value()), group, port);
                return 0;
            }

            // Runners ---------------------------------------------------------

            void Server::start_runner(std::unique_ptr<Connection> connection, const std::string& peer_host,
                                      uint16_t peer_port)
            {
                reap_runners();
                SessionConfig config;
                config.instance    = _instances.fetch_add(1);
                config.kind        = connection->kind();
                config.peer_host   = peer_host;
                config.peer_port   = peer_port;
                config.log         = _log.load();
                config.session_log = _session_log.load();
                auto made          = SessionRunner::create(
                    std::move(connection),
                    [&](SessionOutput& out) {
                        return std::make_shared<Session>(*this, _resolver, _units, _mirror_clock, _exec_clock, out,
                                                         config);
                    },
                    *this, shared_from_this());
                if (!made)
                {
                    message_publish(MSG_ERROR, "Trick VariableServer: could not start a session: %s\n",
                                    made.error().message.c_str());
                    return;
                }
                std::shared_ptr<SessionRunner> runner = made.value();
                _registry.add(runner->session());
                {
                    std::lock_guard<std::mutex> guard(_runners_mutex);
                    _runners.push_back(runner);
                }
                runner->start();
            }

            void Server::reap_runners()
            {
                std::vector<std::shared_ptr<SessionRunner>> done;
                {
                    std::lock_guard<std::mutex> guard(_runners_mutex);
                    for (auto it = _runners.begin(); it != _runners.end();)
                    {
                        if ((*it)->finished())
                        {
                            done.push_back(*it);
                            it = _runners.erase(it);
                        }
                        else
                            ++it;
                    }
                }
                for (auto& r : done)
                    r->join();
            }

            int Server::shutdown()
            {
                {
                    std::lock_guard<std::mutex> guard(_resume_mutex);
                    _stopping.store(true);
                }
                _resume_cv.notify_all();
                {
                    std::lock_guard<std::recursive_mutex> guard(_listen_mutex);
                    stop_listener();
                }
                std::vector<std::shared_ptr<SessionRunner>> runners;
                {
                    std::lock_guard<std::mutex> guard(_runners_mutex);
                    runners.swap(_runners);
                }
                for (auto& r : runners)
                    r->stop();
                const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
                std::size_t left = 0;
                for (auto& r : runners)
                {
                    if (r->wait_until(deadline))
                        r->join();
                    else
                    {
                        ++left;
                        message_publish(MSG_WARNING,
                                        "Trick::VariableServer::shutdown() giving up on a variable server session "
                                        "that did not stop when asked; it is most likely inside a client command. "
                                        "Leaving it so that shutdown can continue.\n");
                        SessionRunner::abandon(r);
                    }
                }
                _reload_lock.reset();
                message_publish(MSG_INFO, "Trick VariableServer: shutdown stopped %zu session(s); %zu did not stop.\n",
                                runners.size() - left, left);
                return 0;
            }

            void Server::shutdown_connections()
            {
                // The old server waited here for a client it was handing to a new session thread.
                // The listener hands clients over without waiting, so only refuse new ones.
                _vs.set_allow_connections(false);
                config_changed();
            }

            // Jobs ---------------------------------------------------------------

            void Server::refresh_job_times(bool force, bool retime)
            {
                if (!force && !_schedule_changed.exchange(false, std::memory_order_acq_rel))
                    return;
                if (force)
                    _schedule_changed.store(false, std::memory_order_relaxed);
                const auto t = _registry.refresh(_exec_clock.time_tics(), _exec_clock.freeze_time_tics(), retime);
                if (_copy_data_job != nullptr)
                    _copy_data_job->next_tics = t.next_tics;
                if (_copy_freeze_job != nullptr)
                    _copy_freeze_job->next_tics = t.freeze_next_tics;
            }

            int Server::copy_and_write_top()
            {
                _mirror_clock.update(_exec_clock);
                refresh_job_times(false);
                _registry.copy_top(_exec_clock.frame_count());
                return 0;
            }

            int Server::copy_and_write_scheduled()
            {
                _mirror_clock.update(_exec_clock);
                refresh_job_times(false);
                const long long now  = _copy_data_job != nullptr ? _copy_data_job->next_tics : _exec_clock.time_tics();
                const long long next = _registry.copy_scheduled(now);
                if (_copy_data_job != nullptr)
                    _copy_data_job->next_tics = next;
                return 0;
            }

            int Server::copy_and_write_freeze_scheduled()
            {
                _mirror_clock.update(_exec_clock);
                refresh_job_times(false);
                const long long now
                    = _copy_freeze_job != nullptr ? _copy_freeze_job->next_tics : _exec_clock.freeze_time_tics();
                const long long next = _registry.copy_freeze_scheduled(now);
                if (_copy_freeze_job != nullptr)
                    _copy_freeze_job->next_tics = next;
                return 0;
            }

            int Server::copy_and_write_freeze()
            {
                _mirror_clock.update(_exec_clock);
                refresh_job_times(false);
                _registry.copy_freeze(_exec_clock.freeze_frame_count());
                return 0;
            }

            int Server::freeze_init()
            {
                _mirror_clock.update(_exec_clock);
                refresh_job_times(false);
                const long long next = _registry.freeze_init();
                if (_copy_freeze_job != nullptr)
                    _copy_freeze_job->next_tics = next;
                return 0;
            }

            int Server::get_next_sync_call_time()
            {
                refresh_job_times(true);
                return 0;
            }

            int Server::get_next_freeze_call_time()
            {
                refresh_job_times(true);
                return 0;
            }

            int Server::suspend_pre_checkpoint_reload()
            {
                _suspended.store(true);
                // Wait for every runner to finish its current read of memory, and keep them out
                // until the reload ends (resume_post_checkpoint_reload).
                _reload_lock = std::make_unique<std::unique_lock<std::shared_mutex>>(_resolver.memory_mutex());
                return 0;
            }

            int Server::resume_post_checkpoint_reload()
            {
                config_changed(); // the checkpoint restored the settings
                if (_reload_lock)
                {
                    _resolver.memory_replaced(); // every name is looked up again before its next copy
                    _reload_lock.reset();
                }
                {
                    std::lock_guard<std::mutex> guard(_resume_mutex);
                    _suspended.store(false);
                }
                _resume_cv.notify_all();
                _mirror_clock.update(_exec_clock);
                refresh_job_times(true, true); // sim time moved: start every schedule again from now
                return 0;
            }

            // ListenPolicy --------------------------------------------------------

            bool Server::accepting()
            {
                // A client that connects during a checkpoint load waits for the load to end, as
                // with the old server (its listen thread paused), instead of being closed.
                if (_suspended.load())
                {
                    std::unique_lock<std::mutex> lock(_resume_mutex);
                    _resume_cv.wait_for(lock, std::chrono::seconds(60), [this] {
                        return !_suspended.load() || _stopping.load() || _listener_stopping.load();
                    });
                }
                return _enabled.load() && _allow.load() && !_suspended.load() && !_stopping.load();
            }

            bool Server::allowed(const Address& client)
            {
                if (_bypass.load())
                    return true;
                std::lock_guard<std::mutex> guard(_filter_mutex);
                return _filter.allows(client);
            }

            void Server::connected(std::unique_ptr<TcpConnection> connection, const Listener&)
            {
                const Address peer = connection->peer();
                start_runner(std::move(connection), peer.host(), peer.port());
            }

            std::string Server::beacon_message(const Listener& listener)
            {
                BeaconInfo info = _beacon_base;
                info.host       = listener.hostname();
                info.port       = listener.port();
                {
                    std::lock_guard<std::mutex> guard(_filter_mutex);
                    info.user_tag = _user_tag;
                }
                info.enabled   = _enabled.load();
                info.exec_mode = _mirror_clock.exec_mode();
                return format_beacon(info);
            }

            void Server::log(const std::string& text, bool error)
            {
                message_publish(error ? MSG_ERROR : MSG_INFO, "%s", with_newline(text).c_str());
            }

            // SessionHost ---------------------------------------------------------

            void Server::read_memory(const std::function<void()>& read)
            {
                if (t_memory_held > 0)
                {
                    read(); // inside a Python line, which holds the lock already
                    return;
                }
                std::shared_lock<std::shared_mutex> lock = lock_shared_releasing_gil(_resolver.memory_mutex());
                MemoryHeld held;
                read();
            }

            Expected<void> Server::run_python(std::string_view text)
            {
                // A Python line can read and write simulation memory (SWIG), so it runs with the
                // memory lock held for reading: a checkpoint load waits for the lines that run, and
                // no line starts while one loads. The lock is taken before the GIL, never after:
                // the main thread holds the lock for writing when it takes the GIL in
                // IPPython::restart.
                {
                    std::unique_lock<std::mutex> lock(_resume_mutex);
                    _resume_cv.wait(lock, [this] { return !_suspended.load() || _stopping.load(); });
                }
                const std::string line(text);
                std::shared_lock<std::shared_mutex> lock = lock_shared_releasing_gil(_resolver.memory_mutex());
                int ret = 0;
                {
                    MemoryHeld held;
                    ret = ip_parse(line.c_str());
                }
                if (ret != 0)
                    return Error { "the Python input processor reported an error" };
                return {};
            }

            int Server::write_memory(const std::function<int()>& write)
            {
                if (t_memory_held > 0) // a Python line: it holds the lock for reading
                    return write();
                // Otherwise take the lock for writing, so no copy reads the value while it changes.
                std::unique_lock<std::shared_mutex> lock = lock_exclusive_releasing_gil(_resolver.memory_mutex());
                return write();
            }

            int Server::var_set(const cmd::VarSet& c)
            {
                const char* units = c.units ? c.units->c_str() : nullptr;
                return write_memory([&] { return assign_variable(c.name.c_str(), c.value, units); });
            }

            std::string Server::sie_file(SieFile which)
            {
                // The runtime SIE directory: sie_append_runtime_objs() may move the resource file there.
                switch (which)
                {
                    case SieFile::Resource:
                        sie_append_runtime_objs();
                        return sie_get_runtime_sie_dir() + "/S_sie.resource";
                    case SieFile::Class:
                        sie_class_attr_map_print_xml();
                        return sie_get_runtime_sie_dir() + "/S_sie_class.xml";
                    case SieFile::Enum:
                        sie_enum_attr_map_print_xml();
                        return sie_get_runtime_sie_dir() + "/S_sie_enum.xml";
                    case SieFile::TopLevelObjects:
                        sie_top_level_objects_print_xml();
                        return sie_get_runtime_sie_dir() + "/S_sie_top_level_objects.xml";
                }
                return std::string();
            }

            void Server::message(LogLevel level, std::string_view text)
            {
                int type = MSG_INFO;
                switch (level)
                {
                    case LogLevel::Info:
                        type = MSG_INFO;
                        break;
                    case LogLevel::Warning:
                        type = MSG_WARNING;
                        break;
                    case LogLevel::Error:
                        type = MSG_ERROR;
                        break;
                    case LogLevel::Debug:
                        type = MSG_DEBUG;
                        break;
                    case LogLevel::Playback:
                        type = MSG_PLAYBACK;
                        break;
                }
                const std::string s(text);
                message_publish(type, "%s", s.c_str());
            }

            void Server::session_log(int instance, std::string_view text)
            {
                int stream = -1;
                {
                    std::lock_guard<std::mutex> guard(_log_mutex);
                    auto it = _session_logs.find(instance);
                    if (it == _session_logs.end())
                    {
                        const std::string name = "VSSession" + std::to_string(instance);
                        stream                 = open_custom_message_file("session_logs/" + name + ".log", name);
                        _session_logs[instance] = stream;
                    }
                    else
                        stream = it->second;
                }
                if (stream < 0)
                    return;
                const std::string s(text);
                message_publish(stream, "%s", s.c_str());
            }

            void Server::local_stdio(int stream, std::string_view text)
            {
                std::FILE* f = stream == 2 ? stderr : stdout;
                std::fwrite(text.data(), 1, text.size(), f);
            }

            void Server::client_tag(std::string_view tag)
            {
                set_thread_name("VS_" + std::string(tag.substr(0, 12)));
            }

            // RunnerHooks -----------------------------------------------------------

            void Server::run(Session& session, const std::function<void()>& work)
            {
                Session* const previous = t_current;
                t_current               = &session;
                try
                {
                    work();
                }
                catch (Trick::ExecutiveException& ex)
                {
                    message_publish(MSG_ERROR,
                                    "\nVARIABLE SERVER COMMANDED exec_terminate\n  ROUTINE: %s\n  DIAGNOSTIC: %s\n",
                                    ex.file.c_str(), ex.message.c_str());
                    exec_signal_terminate();
                    session.request_exit();
                }
                catch (const std::exception& ex)
                {
                    message_publish(MSG_ERROR, "\nVARIABLE SERVER caught std::exception\n  DIAGNOSTIC: %s\n", ex.what());
                    exec_signal_terminate();
                    session.request_exit();
                }
                t_current = previous;
            }

            void Server::started(Session&)
            {
                set_thread_name("VarServSession");
                apply_affinity();
            }

            void Server::finished(Session& session) { _registry.remove(&session); }

            void Server::log(Session& session, const std::string& text, bool error)
            {
                message_publish(error ? MSG_ERROR : MSG_INFO, "Variable Server session %d: %s",
                                session.config().instance, with_newline(text).c_str());
            }

        } // namespace adapter
    } // namespace vs
} // namespace Trick
