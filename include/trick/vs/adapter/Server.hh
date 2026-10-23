/*
PURPOSE: (The rewritten variable server behind Trick::VariableServer: VariableServer::Impl.)

Server is the plan's VariableServer::Impl. The public Trick::VariableServer
keeps its job methods and checkpointed fields; when the rewrite is selected
it forwards each job to its Server. Server owns the listener thread (a
ListenLoop), the session registry, the session runners, the Memory Manager
resolver and the units converter, and it is the SessionHost, ListenPolicy
and RunnerHooks of the core library.

Selection (Phase 5 only): the environment variable TRICK_VS_REWRITE=1, read
when the VariableServer is constructed, selects this server; otherwise the
old one runs. Phase 6 removes the old server and the switch.

Threads:
  * The main thread runs the jobs. It reads the executive directly
    (ExecClock) and publishes a copy for the other threads (MirrorClock).
  * The listener thread runs the ListenLoop: it accepts clients and sends
    the beacon. It reads only atomics and the address filter (under a mutex).
  * Each session runner runs one Session. While it runs a session's work,
    current_session() is that session, so the var_* functions that Python
    calls reach it without a map lookup on pthread_self().

Memory lock: runners read simulation memory under MemoryResolver's shared
lock. preload_checkpoint takes it for writing and keeps it until the
restart jobs end the reload (resumePostCheckpointReload), so no runner reads
memory while the Memory Manager replaces it. A runner that waits for the
lock while it holds the Python GIL lets the GIL go first (the main thread
needs the GIL in IPPython::restart while it holds the lock).

ICG and SWIG never parse this header.
*/

#ifndef TRICK_VS_ADAPTER_SERVER_HH
#define TRICK_VS_ADAPTER_SERVER_HH

#include "trick/vs/AddressFilter.hh"
#include "trick/vs/ListenLoop.hh"
#include "trick/vs/Session.hh"
#include "trick/vs/SessionRegistry.hh"
#include "trick/vs/SessionRunner.hh"
#include "trick/vs/adapter/MemoryResolver.hh"
#include "trick/vs/adapter/UdUnitsConverter.hh"

#include <atomic>
#include <condition_variable>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <shared_mutex>
#include <string>
#include <thread>
#include <vector>

namespace Trick
{
    class VariableServer;
    class JobData;

    namespace vs
    {
        namespace adapter
        {

            /** The executive's clock, read directly. Main thread only. */
            class ExecClock : public Clock
            {
                public:
                    long long time_tics() const override;
                    long long tic_value() const override;
                    long long frame_count() const override;
                    long long freeze_time_tics() const override;
                    long long freeze_frame_count() const override;
                    bool real_time() const override;
                    int exec_mode() const override;
            };

            /** A copy of the executive's clock that the main thread publishes for the other threads. */
            class MirrorClock : public Clock
            {
                public:
                    /** Main thread: copy `from`. */
                    void update(const Clock& from) noexcept;

                    long long time_tics() const override { return _time.load(std::memory_order_relaxed); }
                    long long tic_value() const override { return _tic_value.load(std::memory_order_relaxed); }
                    long long frame_count() const override { return _frame.load(std::memory_order_relaxed); }
                    long long freeze_time_tics() const override { return _freeze_time.load(std::memory_order_relaxed); }
                    long long freeze_frame_count() const override
                    {
                        return _freeze_frame.load(std::memory_order_relaxed);
                    }
                    bool real_time() const override { return _real_time.load(std::memory_order_relaxed); }
                    int exec_mode() const override { return _mode.load(std::memory_order_relaxed); }

                private:
                    std::atomic<long long> _time { 0 };
                    std::atomic<long long> _tic_value { 1000000 };
                    std::atomic<long long> _frame { 0 };
                    std::atomic<long long> _freeze_time { 0 };
                    std::atomic<long long> _freeze_frame { 0 };
                    std::atomic<bool> _real_time { false };
                    std::atomic<int> _mode { 0 };
            };

            /**
             * Lock `m` for reading. If the lock is busy and this thread holds the Python
             * GIL, release the GIL while waiting (VsPythonBridge.cpp).
             */
            std::shared_lock<std::shared_mutex> lock_shared_releasing_gil(std::shared_mutex& m);

            /** Lock `m` for writing, the same way. */
            std::unique_lock<std::shared_mutex> lock_exclusive_releasing_gil(std::shared_mutex& m);

            /**
             * var_set: assign `value` (with optional `units`) to the variable `name`, as the
             * old var_set_base did. Returns 0, 1 if the variable is not an input, 2 if it is
             * not found. The caller holds the memory lock.
             */
            int assign_variable(const char* name, const cmd::SetValue& value, const char* units);

            class Server final : public ListenPolicy,
                                 public SessionHost,
                                 public RunnerHooks,
                                 public std::enable_shared_from_this<Server>
            {
                public:
                    /** `vs` owns the Server (through ServerHandle) and outlives the jobs. */
                    explicit Server(VariableServer& vs);
                    ~Server() override;

                    Server(const Server&)            = delete;
                    Server& operator=(const Server&) = delete;

                    /** True if TRICK_VS_REWRITE=1 selects this server. */
                    static bool selected();

                    /** The Server of the running simulation, or null (old server selected). */
                    static Server* active() noexcept;

                    /** The session whose work this thread runs now, or null. */
                    static Session* current_session() noexcept;

                    // ------------------------------------------------- jobs (main thread)
                    int default_data();
                    int init();
                    int restart();
                    int freeze_init();
                    int shutdown();
                    void shutdown_connections();
                    int copy_and_write_top();
                    int copy_and_write_scheduled();
                    int copy_and_write_freeze_scheduled();
                    int copy_and_write_freeze();
                    int get_next_sync_call_time();
                    int get_next_freeze_call_time();
                    int suspend_pre_checkpoint_reload();
                    int resume_post_checkpoint_reload();
                    void set_copy_data_job(JobData* job) noexcept { _copy_data_job = job; }
                    void set_copy_and_write_freeze_job(JobData* job) noexcept { _copy_freeze_job = job; }

                    // ------------------------------------------------------ configuration
                    int create_tcp_socket(const char* address, unsigned short port);
                    int create_udp_socket(const char* address, unsigned short port);
                    int create_multicast_socket(const char* group, const char* address, unsigned short port);
                    /** Copy the VariableServer's settings (enabled, allowlist, logs) for the other threads. */
                    void config_changed();
                    void set_python_commands(bool on) noexcept { _python.store(on); }
                    std::string connections_json() const { return _registry.connections_json(); }
                    MemoryResolver& resolver() noexcept { return _resolver; }
                    const SessionRegistry& registry() const noexcept { return _registry; }

                    // ------------------------------------------------------- ListenPolicy
                    bool accepting() override;
                    bool allowed(const Address& client) override;
                    void connected(std::unique_ptr<TcpConnection> connection, const Listener& listener) override;
                    std::string beacon_message(const Listener& listener) override;
                    void log(const std::string& message, bool error) override;

                    // -------------------------------------------------------- SessionHost
                    void read_memory(const std::function<void()>& read) override;
                    /** False while disabled, and while a checkpoint loads (no copies then). */
                    bool enabled() const override
                    {
                        return _enabled.load(std::memory_order_relaxed) && !_suspended.load(std::memory_order_relaxed);
                    }
                    Expected<void> run_python(std::string_view text) override;
                    bool python_commands() const override { return _python.load(std::memory_order_relaxed); }
                    int var_set(const cmd::VarSet& command) override;
                    std::string sie_file(SieFile which) override;
                    void schedule_changed() override { _schedule_changed.store(true, std::memory_order_release); }
                    bool info_messages() const override { return _info_msg.load(std::memory_order_relaxed); }
                    void message(LogLevel level, std::string_view text) override;
                    void session_log(int instance, std::string_view text) override;
                    void local_stdio(int stream, std::string_view text) override;
                    void client_tag(std::string_view tag) override;

                    // -------------------------------------------------------- RunnerHooks
                    void run(Session& session, const std::function<void()>& work) override;
                    void started(Session& session) override;
                    void finished(Session& session) override;
                    void log(Session& session, const std::string& text, bool error) override;

                private:
                    void start_runner(std::unique_ptr<Connection> connection, const std::string& peer_host,
                                      uint16_t peer_port);
                    void reap_runners();
                    void stop_listener();
                    Expected<void> start_listener();
                    Expected<Listener> open_main_listener();
                    void refresh_job_times(bool force, bool retime = false);
                    /** Run this thread on the listen thread's CPUs (var_server_cpu_set), as the old threads did. */
                    void apply_affinity();

                    VariableServer& _vs;
                    ExecClock _exec_clock;
                    MirrorClock _mirror_clock;
                    MemoryResolver _resolver;
                    UdUnitsConverter _units;
                    SessionRegistry _registry;

                    // Main thread
                    JobData* _copy_data_job   = nullptr;
                    JobData* _copy_freeze_job = nullptr;
                    std::optional<Listener> _main_listener;
                    std::vector<Listener> _extra_listeners; ///< var_server_create_tcp_socket
                    std::unique_ptr<std::unique_lock<std::shared_mutex>> _reload_lock;
                    bool _initialized = false;

                    // Listener thread
                    std::unique_ptr<ListenLoop> _loop;
                    std::thread _listen_thread;

                    // Runners
                    mutable std::mutex _runners_mutex;
                    std::vector<std::shared_ptr<SessionRunner>> _runners;
                    std::atomic<int> _instances { 0 };

                    // Settings for the other threads
                    std::atomic<bool> _enabled { false };
                    std::atomic<bool> _allow { false };
                    std::atomic<bool> _bypass { false };
                    std::atomic<bool> _info_msg { false };
                    std::atomic<bool> _log { false };
                    std::atomic<bool> _session_log { false };
                    std::atomic<bool> _python { true };
                    std::atomic<bool> _suspended { false };
                    std::atomic<bool> _stopping { false };
                    std::atomic<bool> _schedule_changed { false };
                    std::atomic<bool> _listener_stopping { false };
                    std::mutex _resume_mutex;            ///< with _resume_cv: Python lines wait out a reload
                    std::condition_variable _resume_cv;
                    mutable std::mutex _filter_mutex;
                    AddressFilter _filter;
                    mutable std::mutex _log_mutex;
                    std::map<int, int> _session_logs; ///< instance -> message stream
                    BeaconInfo _beacon_base;          ///< the fields that do not change
                    std::string _user_tag;            ///< under _filter_mutex
                    std::recursive_mutex _listen_mutex; ///< listener changes: main thread or a runner (Python)
            };

            /** What the public VariableServer holds, through a pointer to an incomplete type. */
            struct ServerHandle
            {
                    std::shared_ptr<Server> server;
            };

        } // namespace adapter
    } // namespace vs
} // namespace Trick

#endif
