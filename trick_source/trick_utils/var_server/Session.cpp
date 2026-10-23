#include "trick/vs/Session.hh"

#include "trick/vs/CLocale.hh"
#include "trick/vs/CommandParser.hh"
#include "trick/vs/FixedReply.hh"
#include "trick/vs/TimeVar.hh"
#include "trick/vs/Units.hh"

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <stdexcept>
#include <type_traits>
#include <utility>

namespace Trick
{
    namespace vs
    {

        SessionHost::~SessionHost()     = default;
        SessionOutput::~SessionOutput() = default;

        namespace
        {
            template <class... Args> std::string format(const char* fmt, Args... args)
            {
                char buf[512];
                const int n = std::snprintf(buf, sizeof buf, fmt, args...);
                if (n < 0)
                    return std::string();
                if (static_cast<std::size_t>(n) < sizeof buf)
                    return std::string(buf, static_cast<std::size_t>(n));
                std::string out(static_cast<std::size_t>(n) + 1, '\0');
                std::snprintf(&out[0], out.size(), fmt, args...);
                out.resize(static_cast<std::size_t>(n));
                return out;
            }

            double seconds(long long tics, long long per) noexcept
            {
                return per > 0 ? static_cast<double>(tics) / static_cast<double>(per) : 0.0;
            }

            /** A JSON string body: quotes, backslashes and control characters escaped. */
            void append_json_text(std::string& out, const std::string& text)
            {
                for (const char ch : text)
                {
                    const unsigned char c = static_cast<unsigned char>(ch);
                    if (c == '"' || c == '\\')
                    {
                        out += '\\';
                        out += ch;
                    }
                    else if (c < 0x20)
                    {
                        char esc[8];
                        std::snprintf(esc, sizeof esc, "\\u%04x", c);
                        out += esc;
                    }
                    else
                        out += ch;
                }
            }
        } // namespace

        Session::Session(SessionHost& host, Resolver& resolver, UnitConverter& units, const Clock& runner_clock,
                         const Clock& main_clock, SessionOutput& output, SessionConfig config)
            : _host(host)
            , _resolver(resolver)
            , _units(units)
            , _runner_clock(runner_clock)
            , _main_clock(main_clock)
            , _output(output)
            , _config(std::move(config))
            , _schedule(default_schedule(runner_clock.tic_value()))
        {
            _log.store(_config.log, std::memory_order_relaxed);
            _session_log.store(_config.session_log, std::memory_order_relaxed);
            auto empty = std::make_shared<VariableList>();
            _list      = empty;
            std::atomic_store(&_published_list, std::shared_ptr<const VariableList>(empty));
            std::atomic_store(&_published_schedule, std::make_shared<const Schedule>(_schedule));
            publish_info();
        }

        Session::~Session() = default;

        // ------------------------------------------------------------------
        // Logs
        // ------------------------------------------------------------------

        std::string Session::prefix() const
        {
            const double t = seconds(_runner_clock.time_tics(), _runner_clock.tic_value());
            return format("tag=<%s> time=%f ", _tag.c_str(), t);
        }

        void Session::log_error(const std::string& text)
        {
            _host.message(LogLevel::Error, text);
            log_session(text);
        }

        void Session::log_debug(int level, const std::string& text)
        {
            if (_debug >= level)
                _host.message(LogLevel::Debug, text);
        }

        void Session::log_session(const std::string& text)
        {
            if (_session_log.load(std::memory_order_relaxed))
                _host.session_log(_config.instance, text);
        }

        void Session::publish_info()
        {
            auto info     = std::make_shared<Info>();
            info->tag     = _tag;
            info->binary  = _binary;
            info->cycle_s = _schedule.cycle_s;
            for (const ListEntry& e : _list->entries)
                info->names.push_back(e.var->name());
            std::atomic_store(&_published_info, std::shared_ptr<const Info>(std::move(info)));
        }

        std::string Session::connection_json() const
        {
            ScopedCLocale c_locale;
            const std::shared_ptr<const Info> info = std::atomic_load(&_published_info);
            // The layout of the old VariableServerSessionThread and VariableServerSession operator<<.
            std::string out = "  \"connection\":{\n";
            out += "    \"client_tag\":\"";
            append_json_text(out, info->tag);
            out += "\",\n    \"client_IP_address\":\"";
            append_json_text(out, _config.peer_host);
            out += "\",\n";
            out += format("    \"client_port\":\"%u\",\n", static_cast<unsigned>(_config.peer_port));
            out += info->binary ? "    \"format\":\"BINARY\",\n" : "    \"format\":\"ASCII\",\n";
            out += format("    \"update_rate\":%g,\n", info->cycle_s);
            out += "    \"variables\":[\n";
            for (std::size_t i = 0; i < info->names.size(); ++i)
            {
                out += "      \"";
                append_json_text(out, info->names[i]);
                out += '"';
                if (i + 1 < info->names.size())
                    out += ',';
                out += '\n';
            }
            out += "    ]\n  }\n";
            return out;
        }

        // ------------------------------------------------------------------
        // Runner thread: commands
        // ------------------------------------------------------------------

        void Session::start()
        {
            log_session(format("Variable Server Session started with %s:%u\n", _config.peer_host.c_str(),
                               static_cast<unsigned>(_config.peer_port)));
        }

        void Session::handle_batch(std::string_view text)
        {
            const std::string message(text);
            if (_log.load(std::memory_order_relaxed))
                _host.message(LogLevel::Playback, prefix() + message);
            log_session(prefix() + message);
            log_debug(3, format("tag=<%s> var_server received bytes = msg_len = %zu\n", _tag.c_str(), message.size()));
            if (_debug >= 1 || _host.info_messages())
                _host.message(LogLevel::Debug, prefix() + message);

            for (const Command& c : parse_batch(text))
            {
                execute(c);
                if (exiting())
                    break;
            }
        }

        void Session::execute(const Command& command)
        {
            // While a file is being sent, its bytes must not mix with other replies:
            // commands wait, in order, until it is sent.
            if (_file)
            {
                if (_draining)
                    _waiting.insert(_waiting.begin() + static_cast<std::ptrdiff_t>(_insert_at++), command);
                else
                    _waiting.push_back(command);
                return;
            }
            if (!_waiting.empty() && !_draining)
            {
                _waiting.push_back(command);
                return;
            }
            std::visit([this](const auto& c) { this->run(c); }, command);
        }

        template <class C> void Session::run(const C&)
        {
            static_assert(!std::is_same<C, C>::value, "every command needs a run()");
        }

        // Variable list -------------------------------------------------------

        std::unique_ptr<ResolvedVar> Session::resolve(const std::string& name)
        {
            if (name == TimeVar::variable_name)
                return std::make_unique<TimeVar>();
            std::unique_ptr<ResolvedVar> var;
            _host.read_memory([&] { var = _resolver.resolve(name); });
            return var;
        }

        ListEntry Session::make_entry(const std::string& name)
        {
            ListEntry e;
            e.var = resolve(name);
            if (name == TimeVar::variable_name)
                e.units = "s"; // the time variable always prints {s}
            if (!e.var->resolved())
            {
                std::string text = "Variable Server could not find variable " + name + ".\n";
                const std::string note = e.var->take_note();
                if (!note.empty())
                    text = "Variable Server could not find variable " + name + ": " + note + ".\n";
                log_error(text);
            }
            return e;
        }

        void Session::set_list(std::vector<ListEntry> entries)
        {
            auto list     = std::make_shared<VariableList>();
            list->version = ++_list_versions;
            list->entries = std::move(entries);
            list->vars.reserve(list->entries.size());
            for (const ListEntry& e : list->entries)
                list->vars.push_back(e.var.get());
            _list = list;
            std::atomic_store(&_published_list, std::shared_ptr<const VariableList>(list));
            _frame_unsent = false; // a frame from the old list is never sent
            publish_info();
        }

        void Session::set_units(std::vector<ListEntry>& entries, const std::string& name, const std::string& units)
        {
            for (ListEntry& e : entries)
            {
                if (e.var->name() != name)
                    continue;
                auto choice = choose_units(*e.var, units, _units);
                if (!choice)
                    log_error("Variable Server: " + choice.error().message + "\n");
                else if (choice.value())
                {
                    e.conversion = choice.value()->conversion;
                    e.units      = choice.value()->units;
                }
                return; // the first match only, as the old server
            }
        }

        void Session::run(const cmd::VarAdd& c)
        {
            std::vector<ListEntry> entries = _list->entries;
            entries.push_back(make_entry(c.name));
            if (c.units)
                set_units(entries, c.name, *c.units);
            set_list(std::move(entries));
        }

        void Session::run(const cmd::VarRemove& c)
        {
            std::vector<ListEntry> entries = _list->entries;
            for (auto it = entries.begin(); it != entries.end(); ++it)
            {
                if (it->var->name() == c.name)
                {
                    entries.erase(it);
                    set_list(std::move(entries));
                    return;
                }
            }
        }

        void Session::run(const cmd::VarUnits& c)
        {
            std::vector<ListEntry> entries = _list->entries;
            set_units(entries, c.name, c.units);
            set_list(std::move(entries));
        }

        void Session::run(const cmd::VarClear&) { set_list({}); }

        // Sending -------------------------------------------------------------

        void Session::sample(Snapshot& out, const std::vector<ResolvedVar*>& vars, const Clock& clock, bool shared)
        {
            const uint64_t sequence = out.sequence;
            out.clear();
            out.sequence  = sequence + 1;
            out.time_tics = clock.time_tics();
            out.time_s    = seconds(out.time_tics, clock.tic_value());
            const bool validate = _validate.load(std::memory_order_relaxed);
            auto stage_all      = [&] {
                _host.read_memory([&] {
                    for (ResolvedVar* v : vars)
                        v->stage(out, validate);
                });
            };
            if (shared)
            {
                std::lock_guard<std::mutex> guard(_stage_mutex);
                stage_all();
            }
            else
                stage_all();
        }

        void Session::collect_notes(const std::vector<ResolvedVar*>& vars)
        {
            for (ResolvedVar* v : vars)
            {
                const std::string note = v->take_note();
                if (!note.empty())
                    log_session(prefix() + note + "\n");
            }
        }

        bool Session::send(std::string_view message)
        {
            if (exiting())
                return false;
            if (!_output.send(message))
            {
                log_error(format("tag=<%s> Variable Server: the client is not reading; its send queue is full. "
                                 "Closing the connection.\n",
                                 _tag.c_str()));
                request_exit();
                return false;
            }
            return true;
        }

        void Session::send_values(const Snapshot& snapshot, const VariableList& list, MessageType type)
        {
            std::vector<VarFormat> formats;
            formats.reserve(list.entries.size());
            for (const ListEntry& e : list.entries)
            {
                VarFormat f;
                f.name       = e.var->name();
                f.conversion = e.conversion.get();
                f.units      = e.units;
                formats.push_back(f);
            }
            _packets.clear();
            if (_binary)
                encode_binary(_packets, snapshot, formats, type, _nonames, _byteswap);
            else
                encode_ascii(_packets, snapshot, formats, type);
            for (const std::string& w : _packets.warnings)
                _host.message(LogLevel::Warning, format("tag=<%s> ", _tag.c_str()) + w);
            for (const std::string& m : _packets.messages)
            {
                log_debug(2, format("tag=<%s> var_server sending %zu bytes\n", _tag.c_str(), m.size()));
                if (!send(m))
                    return;
            }
        }

        void Session::run(const cmd::VarSend&)
        {
            const std::shared_ptr<const VariableList> list = _list;
            sample(_async_snapshot, list->vars, _runner_clock, true);
            collect_notes(list->vars);
            send_values(_async_snapshot, *list, MessageType::VarList);
        }

        void Session::run(const cmd::VarSendOnce& c)
        {
            const std::vector<std::string> names = split_send_once_names(c.names);
            const int count                      = c.count ? *c.count : 1;
            if (count < 0 || names.size() != static_cast<std::size_t>(count))
            {
                log_error(format("Number of variables sent to var_send_once (%zu) does not match num_vars (%d).\n",
                                 names.size(), count));
                return;
            }
            VariableList once;
            for (const std::string& n : names)
            {
                ListEntry e;
                e.var = resolve(n);
                once.entries.push_back(e);
                once.vars.push_back(once.entries.back().var.get());
            }
            Snapshot snapshot;
            sample(snapshot, once.vars, _runner_clock, false);
            collect_notes(once.vars);
            send_values(snapshot, once, MessageType::SendOnce);
        }

        void Session::run(const cmd::VarExists& c)
        {
            bool exists = false;
            _host.read_memory([&] { exists = _resolver.resolve(c.name)->resolved(); });
            send(var_exists_reply(exists, _binary));
        }

        void Session::run(const cmd::VarGetStlSize& c)
        {
            std::optional<int64_t> size;
            _host.read_memory([&] { size = _resolver.resolve(c.name)->stl_size(); });
            log_debug(2, format("tag=<%s> var_server sending STL size\n", _tag.c_str()));
            send(stl_size_reply(size, _binary));
        }

        void Session::run(const cmd::VarSendListSize&)
        {
            send(list_size_reply(static_cast<int32_t>(_list->entries.size()), _binary));
        }

        // Timing and modes ----------------------------------------------------

        void Session::set_schedule(const Schedule& schedule, bool timing_changed)
        {
            _schedule = schedule;
            std::atomic_store(&_published_schedule, std::make_shared<const Schedule>(schedule));
            if (timing_changed)
            {
                _timing_generation.fetch_add(1, std::memory_order_acq_rel);
                _host.schedule_changed();
            }
            publish_info();
        }

        void Session::run(const cmd::VarCycle& c)
        {
            auto tics = cycle_to_tics(c.seconds, _runner_clock.tic_value());
            if (!tics)
            {
                log_error("Variable Server: " + tics.error().message + "\n");
                return;
            }
            Schedule s   = _schedule;
            s.cycle_s    = c.seconds;
            s.cycle_tics = tics.value();
            set_schedule(s, true);
        }

        void Session::run(const cmd::VarPause&)
        {
            Schedule s = _schedule;
            s.paused   = true;
            set_schedule(s, false);
        }

        void Session::run(const cmd::VarUnpause&)
        {
            Schedule s = _schedule;
            s.paused   = false;
            set_schedule(s, false);
        }

        void Session::run(const cmd::VarSetCopyMode& c)
        {
            auto mode = copy_mode_from_int(c.mode);
            if (!mode)
            {
                log_error("Variable Server: " + mode.error().message + "\n");
                return;
            }
            Schedule s  = _schedule;
            s.copy_mode = mode.value();
            set_schedule(s, true);
        }

        void Session::run(const cmd::VarSetWriteMode& c)
        {
            auto mode = write_mode_from_int(c.mode);
            if (!mode)
            {
                log_error("Variable Server: " + mode.error().message + "\n");
                return;
            }
            Schedule s   = _schedule;
            s.write_mode = mode.value();
            set_schedule(s, false);
        }

        void Session::run(const cmd::VarSync& c)
        {
            const auto modes = sync_modes(c.mode);
            Schedule s       = _schedule;
            s.copy_mode      = modes.first;
            s.write_mode     = modes.second;
            set_schedule(s, true);
        }

        void Session::run(const cmd::VarSetFrameMultiple& c)
        {
            auto ok = check_frame_multiple(c.multiple);
            if (!ok)
            {
                log_error("Variable Server: var_set_frame_multiple: " + ok.error().message + "\n");
                return;
            }
            Schedule s       = _schedule;
            s.frame_multiple = c.multiple;
            set_schedule(s, false);
        }

        void Session::run(const cmd::VarSetFrameOffset& c)
        {
            Schedule s     = _schedule;
            s.frame_offset = c.offset;
            set_schedule(s, false);
        }

        void Session::run(const cmd::VarSetFreezeFrameMultiple& c)
        {
            auto ok = check_frame_multiple(c.multiple);
            if (!ok)
            {
                log_error("Variable Server: var_set_freeze_frame_multiple: " + ok.error().message + "\n");
                return;
            }
            Schedule s              = _schedule;
            s.freeze_frame_multiple = c.multiple;
            set_schedule(s, false);
        }

        void Session::run(const cmd::VarSetFreezeFrameOffset& c)
        {
            Schedule s            = _schedule;
            s.freeze_frame_offset = c.offset;
            set_schedule(s, false);
        }

        // Format and settings --------------------------------------------------

        void Session::run(const cmd::VarAscii&)
        {
            _binary = false;
            publish_info();
        }

        void Session::run(const cmd::VarBinary&)
        {
            _binary = true; // "no names" stays as var_binary_nonames set it (old server)
            publish_info();
        }

        void Session::run(const cmd::VarBinaryNoNames&)
        {
            _binary  = true;
            _nonames = true;
            publish_info();
        }

        void Session::run(const cmd::VarByteswap& c) { _byteswap = c.on; }

        void Session::run(const cmd::VarValidateAddress& c) { _validate.store(c.on, std::memory_order_relaxed); }

        void Session::run(const cmd::VarDebug& c) { _debug = c.level; }

        void Session::run(const cmd::VarSetClientTag& c)
        {
            _tag = c.tag;
            _host.client_tag(c.tag);
            publish_info();
        }

        void Session::run(const cmd::VarSetSendStdio& c) { _send_stdio = c.on; }

        void Session::run(const cmd::VarWriteStdio& c)
        {
            if (_capturing && c.stream == 2)
                _captured += c.text;
            if (_send_stdio)
                send(stdio_reply(c.stream, c.text));
            else
                _host.local_stdio(c.stream, c.text);
        }

        void Session::run(const cmd::VarServerLog& c) { _log.store(c.on, std::memory_order_relaxed); }

        void Session::run(const cmd::VarSendIpErrors& c) { _ip_errors = c.on; }

        void Session::run(const cmd::VarExit&) { request_exit(); }

        // Files ---------------------------------------------------------------

        void Session::start_file(const std::string& path)
        {
            log_debug(2, format("tag=<%s> var_server opening %s.\n", _tag.c_str(), path.c_str()));
            std::FILE* f = std::fopen(path.c_str(), "rb");
            long size    = -1;
            if (f != nullptr && std::fseek(f, 0, SEEK_END) == 0)
            {
                size = std::ftell(f);
                std::rewind(f);
            }
            if (f == nullptr || size < 0)
            {
                if (f != nullptr)
                    std::fclose(f);
                log_error("Variable Server Error: Cannot open " + path + ".\n");
                send(file_missing_reply());
                return;
            }
            if (!send(file_header(static_cast<uint64_t>(size))))
            {
                std::fclose(f);
                return;
            }
            _file.reset(f);
            continue_file();
        }

        void Session::continue_file()
        {
            if (_file)
            {
                std::string chunk;
                while (_file && !exiting())
                {
                    const std::size_t want = std::min(_output.file_chunk(), _output.space());
                    if (want == 0)
                        return; // the queue is full; the runner calls again after a flush
                    chunk.resize(want);
                    const std::size_t got = std::fread(&chunk[0], 1, want, _file.get());
                    if (got > 0 && !send(std::string_view(chunk.data(), got)))
                        return;
                    if (got < want)
                    {
                        if (std::ferror(_file.get()))
                            log_error("Variable Server Error: Failed to read a file it was sending.\n");
                        _file.reset();
                    }
                }
            }
            // The file is sent: run the commands that waited for it, in order.
            if (!_draining)
            {
                _draining = true;
                while (!_file && !_waiting.empty() && !exiting())
                {
                    Command c = std::move(_waiting.front());
                    _waiting.pop_front();
                    _insert_at = 0; // commands this one runs (through Python) go first
                    std::visit([this](const auto& cmd) { this->run(cmd); }, c);
                }
                _draining = false;
            }
        }

        void Session::run(const cmd::SendSieResource&) { start_file(_host.sie_file(SieFile::Resource)); }

        void Session::run(const cmd::SendSieClass&) { start_file(_host.sie_file(SieFile::Class)); }

        void Session::run(const cmd::SendSieEnum&) { start_file(_host.sie_file(SieFile::Enum)); }

        void Session::run(const cmd::SendSieTopLevelObjects&) { start_file(_host.sie_file(SieFile::TopLevelObjects)); }

        void Session::run(const cmd::SendFile& c) { start_file(c.path); }

        // Writes and Python ---------------------------------------------------

        void Session::run(const cmd::VarSet& c) { _host.var_set(c); }

        void Session::run(const cmd::Fallback& c)
        {
            if (!_host.python_commands())
            {
                const std::string text = "Python commands are turned off (var_server_set_python_commands); "
                                         "this line was not run: "
                                         + c.text + "\n";
                _host.message(LogLevel::Warning, prefix() + text);
                log_session(prefix() + text);
                if (_ip_errors)
                    send(ip_error_reply(text));
                return;
            }
            _capturing = true;
            _captured.clear();
            const Expected<void> result = _host.run_python(c.text);
            _capturing = false;
            if (!result)
            {
                std::string text = _captured.empty() ? result.error().message + "\n" : _captured;
                log_session(prefix() + "Python error:\n" + text);
                log_debug(1, prefix() + "Python error:\n" + text);
                if (_ip_errors)
                    send(ip_error_reply(text));
            }
            _captured.clear();
        }

        // ------------------------------------------------------------------
        // Runner thread: asynchronous copies and writes
        // ------------------------------------------------------------------

        void Session::send_frame()
        {
            _frame_unsent = false;
            const Frame& f = _frames.front();
            if (f.list != _list)
                return; // copied from an older list: not every variable is in it
            send_values(f.snapshot, *f.list, MessageType::VarList);
        }

        void Session::on_deadline()
        {
            if (!_host.enabled() || busy())
                return;
            const Schedule& s       = _schedule;
            const bool write_async = s.write_mode == WriteMode::Async
                                  || (s.copy_mode == CopyMode::Async && s.write_mode == WriteMode::WhenCopied)
                                  || !_runner_clock.real_time();
            if (_frames.take())
                _frame_unsent = true;
            if (s.paused || !write_async)
                return;
            if (s.copy_mode == CopyMode::Async)
            {
                const std::shared_ptr<const VariableList> list = _list;
                sample(_async_snapshot, list->vars, _runner_clock, true);
                collect_notes(list->vars);
                send_values(_async_snapshot, *list, MessageType::VarList);
            }
            else if (_frame_unsent)
                send_frame();
        }

        void Session::on_wake()
        {
            if (_frames.take())
                _frame_unsent = true;
            if (!_frame_unsent || busy() || _schedule.paused)
                return;
            if (_frames.front().send_now)
                send_frame();
        }

        // ------------------------------------------------------------------
        // Main thread
        // ------------------------------------------------------------------

        void Session::main_refresh(long long time_tics, long long freeze_time_tics, bool force)
        {
            const uint64_t generation = _timing_generation.load(std::memory_order_acquire);
            if (generation == _main_generation && !force)
                return;
            _main_generation = generation;
            const std::shared_ptr<const Schedule> s = std::atomic_load(&_published_schedule);
            if (s->copy_mode == CopyMode::Scheduled && s->cycle_tics > 0)
            {
                _next_tics        = first_scheduled_tics(std::max(0LL, time_tics), s->cycle_tics);
                _freeze_next_tics = first_scheduled_tics(std::max(0LL, freeze_time_tics), s->cycle_tics);
            }
            else
            {
                _next_tics        = never_tics;
                _freeze_next_tics = never_tics;
            }
        }

        void Session::main_copy(const Schedule& schedule)
        {
            Frame& f                   = _frames.back();
            f.list                     = std::atomic_load(&_published_list);
            const bool send_now        = !schedule.paused && schedule.write_mode == WriteMode::WhenCopied
                                    && _main_clock.real_time();
            f.send_now                 = send_now;
            sample(f.snapshot, f.list->vars, _main_clock, true);
            _frames.publish(); // f now belongs to the runner
            if (send_now && _waker)
                _waker();
        }

        void Session::main_copy_scheduled(long long curr_tics)
        {
            if (!_host.enabled() || exiting())
                return;
            const std::shared_ptr<const Schedule> s = std::atomic_load(&_published_schedule);
            if (s->copy_mode != CopyMode::Scheduled || _next_tics > curr_tics)
                return;
            main_copy(*s);
            _next_tics = curr_tics + s->cycle_tics;
        }

        void Session::main_copy_freeze_scheduled(long long curr_tics)
        {
            if (!_host.enabled() || exiting())
                return;
            const std::shared_ptr<const Schedule> s = std::atomic_load(&_published_schedule);
            if (s->copy_mode != CopyMode::Scheduled || _freeze_next_tics > curr_tics)
                return;
            main_copy(*s);
            _freeze_next_tics = curr_tics + s->cycle_tics;
        }

        void Session::main_copy_top(long long frame)
        {
            if (!_host.enabled() || exiting())
                return;
            const std::shared_ptr<const Schedule> s = std::atomic_load(&_published_schedule);
            if (s->copy_mode != CopyMode::TopOfFrame || !top_of_frame_due(frame, s->frame_multiple, s->frame_offset))
                return;
            main_copy(*s);
        }

        void Session::main_copy_freeze(long long freeze_frame)
        {
            if (!_host.enabled() || exiting())
                return;
            const std::shared_ptr<const Schedule> s = std::atomic_load(&_published_schedule);
            if (s->copy_mode != CopyMode::TopOfFrame
                || !top_of_frame_due(freeze_frame, s->freeze_frame_multiple, s->freeze_frame_offset))
                return;
            main_copy(*s);
        }

        void Session::main_freeze_init()
        {
            const std::shared_ptr<const Schedule> s = std::atomic_load(&_published_schedule);
            if (_host.enabled() && s->copy_mode == CopyMode::Scheduled)
                _freeze_next_tics = s->cycle_tics; // as the old server: one cycle into freeze
            else
                _freeze_next_tics = never_tics;
        }

    } // namespace vs
} // namespace Trick
