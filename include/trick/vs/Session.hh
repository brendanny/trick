/*
PURPOSE: (One client of the variable server: its variable list, modes, timing and output format.)

A Session holds what the old VariableServerSession held, with the rules of
the old server (VariableServerSession*.cpp), and the changes on purpose in
the rewrite plan. It does no socket I/O and starts no thread. Its owner, a
SessionRunner, gives it the lines the client sends and a SessionOutput to
send to; the simulation main thread calls the main_* functions from the
variable server jobs.

Threads. Two threads use a Session:

  * The runner thread owns it. It runs the commands (handle_batch,
    execute), the asynchronous copies and writes (on_deadline), and sends
    what the main thread copied (on_wake). Only this thread changes the
    variable list, the schedule or the output format, and only this thread
    sends.

  * The main thread runs the main_* functions. It reads the variable list
    and the schedule only through the copies the runner publishes
    (std::atomic_store of a std::shared_ptr<const T>), so a list never
    changes under it. It copies values into the producer slot of a triple
    buffer and wakes the runner. It owns next_tics and freeze_next_tics.

Both threads stage the same ResolvedVar objects (the main thread for
scheduled and top-of-frame copies, the runner for var_send and
asynchronous copies), so staging is serialized by a mutex per session. The
mutex is held only while values are copied from memory, never during I/O
or Python.

A new list or schedule replaces the old one; a snapshot carries the list it
was copied from, so the runner encodes it with that list's names and units.
A snapshot from an older list is not sent: the old server sent only when
every variable in the list had been copied since the last send.
*/

#ifndef TRICK_VS_SESSION_HH
#define TRICK_VS_SESSION_HH

#include "trick/vs/Command.hh"
#include "trick/vs/Connection.hh"
#include "trick/vs/Expected.hh"
#include "trick/vs/Interfaces.hh"
#include "trick/vs/Packetizer.hh"
#include "trick/vs/Schedule.hh"
#include "trick/vs/Snapshot.hh"
#include "trick/vs/TripleBuffer.hh"

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <deque>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <string_view>
#include <vector>

namespace Trick
{
    namespace vs
    {

        /** One variable in a session's list. */
        struct ListEntry
        {
                std::shared_ptr<ResolvedVar> var;
                /** The conversion to the requested units; null for none. ASCII only. */
                std::shared_ptr<const Conversion> conversion;
                /** The requested units, printed as " {units}" in ASCII; empty for none. */
                std::string units;
        };

        /** A session's variable list. Never changed once published: a change makes a new list. */
        struct VariableList
        {
                uint64_t version = 0;
                std::vector<ListEntry> entries;
                /** entries[i].var.get(), in order, for staging. */
                std::vector<ResolvedVar*> vars;
        };

        /** Values the main thread copied, and the list they were copied from. */
        struct Frame
        {
                Snapshot snapshot;
                std::shared_ptr<const VariableList> list;
                /** WRITE_WHEN_COPIED in real time: the runner sends this frame as soon as it wakes. */
                bool send_now = false;
        };

        /** The files send_sie_* sends. */
        enum class SieFile
        {
            Resource,
            Class,
            Enum,
            TopLevelObjects
        };

        /** Message levels, as the Trick message system has them. */
        enum class LogLevel
        {
            Info,
            Warning,
            Error,
            Debug,
            Playback
        };

        /** What a session needs from the server around it. The adapter implements it with Trick. */
        class SessionHost
        {
            public:
                virtual ~SessionHost();

                /**
                 * Run `read` with simulation memory locked for reading: staging, looking a
                 * name up, sizing an STL container. A checkpoint load cannot replace memory
                 * while `read` runs.
                 */
                virtual void read_memory(const std::function<void()>& read) = 0;

                /** False while the variable server is disabled: no copies, no writes. */
                virtual bool enabled() const = 0;

                /** Run a line that is not a typed command (the Python input processor). */
                virtual Expected<void> run_python(std::string_view text) = 0;

                /** var_server_set_python_commands (decision 4): false refuses lines that are not typed. */
                virtual bool python_commands() const = 0;

                /** var_set. Returns 0, or the old var_set's code: 1 not an input, 2 not found. */
                virtual int var_set(const cmd::VarSet& command) = 0;

                /** Write a SIE file and give its path. */
                virtual std::string sie_file(SieFile which) = 0;

                /** A session's copy timing changed: the main thread must recompute job times. */
                virtual void schedule_changed() = 0;

                /** set_var_server_info_msg_on: every session logs what it receives. */
                virtual bool info_messages() const = 0;

                /** A message to the Trick message system. */
                virtual void message(LogLevel level, std::string_view text) = 0;

                /** A line for the session's own log file (session_logs/VSSession<instance>.log). */
                virtual void session_log(int instance, std::string_view text) = 0;

                /** Text for the simulation's stdout (1) or stderr (2), when the session does not take it. */
                virtual void local_stdio(int stream, std::string_view text) = 0;

                /** var_set_client_tag: the tag changed (the adapter names the runner thread). */
                virtual void client_tag(std::string_view tag) = 0;
        };

        /** Where a session's replies go. The runner implements it with its Connection. */
        class SessionOutput
        {
            public:
                virtual ~SessionOutput();

                /** Queue a message. False if the queue is full: the session then drops the client. */
                virtual bool send(std::string_view message) = 0;

                /** Free bytes in the queue. A file is sent in chunks only while they fit. */
                virtual std::size_t space() const = 0;

                /** The largest chunk of a file to queue as one message (one datagram for UDP). */
                virtual std::size_t file_chunk() const = 0;
        };

        /** How a session was opened. */
        struct SessionConfig
        {
                /** The number in the session log name, VSSession<instance>. */
                int instance = 0;
                ConnectionKind kind = ConnectionKind::Tcp;
                /** The client's address and port, for the logs and the connection list. */
                std::string peer_host;
                uint16_t peer_port = 0;
                /** The server's settings when the client connected. */
                bool log         = false;
                bool session_log = false;
        };

        class Session
        {
            public:
                /**
                 * `runner_clock` is read on the runner thread, `main_clock` on the main
                 * thread; for a simulation they differ (the runner reads a copy the main
                 * thread publishes). All references must outlive the Session.
                 */
                Session(SessionHost& host, Resolver& resolver, UnitConverter& units, const Clock& runner_clock,
                        const Clock& main_clock, SessionOutput& output, SessionConfig config);
                ~Session();

                Session(const Session&)            = delete;
                Session& operator=(const Session&) = delete;

                // ---------------------------------------------------------- runner thread

                /** Log that the session started (session log). Call once, before the first batch. */
                void start();

                /** Log, parse and run one batch of lines from the client. */
                void handle_batch(std::string_view text);

                /**
                 * Run one command. The var_* functions call this while Python runs a line for
                 * this session. A command that arrives while a file is being sent waits until
                 * the file is sent, so replies stay in order.
                 */
                void execute(const Command& command);

                /** The asynchronous cycle (var_cycle): copy and write as the old async loop did. */
                void on_deadline();

                /** The main thread published a frame: send it now if it must be. */
                void on_wake();

                /** Send more of a file that is being sent, while the queue has space. */
                void continue_file();

                /** True when the session should end: var_exit, or the client is not reading. */
                bool exiting() const noexcept { return _exit.load(std::memory_order_acquire); }

                /** End the session (the client closed the connection, or the server stops). */
                void request_exit() noexcept { _exit.store(true, std::memory_order_release); }

                /** The var_cycle period, in seconds. */
                double cycle_s() const noexcept { return _schedule.cycle_s; }

                /** True while a file is being sent or commands wait for it. */
                bool busy() const noexcept { return _file != nullptr || !_waiting.empty(); }

                // ------------------------------------------------------------ any thread

                /** The server's log settings changed (set_var_server_log_on, ...). */
                void set_server_log(bool on) noexcept { _log.store(on, std::memory_order_relaxed); }
                void set_server_session_log(bool on) noexcept { _session_log.store(on, std::memory_order_relaxed); }

                /** This session as the old server listed it (the CivetWeb vs_connections handler). */
                std::string connection_json() const;

                /** Set before the runner starts: wakes the runner (main thread). */
                void set_waker(std::function<void()> waker) { _waker = std::move(waker); }

                const SessionConfig& config() const noexcept { return _config; }

                // ------------------------------------------------------------ main thread

                /**
                 * If the copy timing changed since the last call (var_set_copy_mode, var_sync,
                 * var_cycle), or `force` is set (sim time jumped: a checkpoint load), set
                 * next_tics and freeze_next_tics as var_set_copy_mode did: the next multiple of
                 * the cycle in scheduled mode, else never.
                 */
                void main_refresh(long long time_tics, long long freeze_time_tics, bool force = false);

                /** copy_and_write_scheduled: copy if scheduled and due at `curr_tics`. */
                void main_copy_scheduled(long long curr_tics);

                /** copy_and_write_freeze_scheduled. */
                void main_copy_freeze_scheduled(long long curr_tics);

                /** copy_and_write_top: copy if top of frame and this frame is selected. */
                void main_copy_top(long long frame);

                /** copy_and_write_freeze. */
                void main_copy_freeze(long long freeze_frame);

                /** freeze_init: a scheduled session copies one cycle into freeze. */
                void main_freeze_init();

                long long next_tics() const noexcept { return _next_tics; }
                long long freeze_next_tics() const noexcept { return _freeze_next_tics; }

            private:
                struct Info
                {
                        std::string tag;
                        bool binary = false;
                        double cycle_s = default_cycle_s;
                        std::vector<std::string> names;
                };

                template <class C> void run(const C& command);

                // Commands
                void run(const cmd::VarAdd& c);
                void run(const cmd::VarRemove& c);
                void run(const cmd::VarUnits& c);
                void run(const cmd::VarClear& c);
                void run(const cmd::VarSend& c);
                void run(const cmd::VarSendOnce& c);
                void run(const cmd::VarExists& c);
                void run(const cmd::VarGetStlSize& c);
                void run(const cmd::VarSendListSize& c);
                void run(const cmd::VarCycle& c);
                void run(const cmd::VarPause& c);
                void run(const cmd::VarUnpause& c);
                void run(const cmd::VarSetCopyMode& c);
                void run(const cmd::VarSetWriteMode& c);
                void run(const cmd::VarSync& c);
                void run(const cmd::VarSetFrameMultiple& c);
                void run(const cmd::VarSetFrameOffset& c);
                void run(const cmd::VarSetFreezeFrameMultiple& c);
                void run(const cmd::VarSetFreezeFrameOffset& c);
                void run(const cmd::VarAscii& c);
                void run(const cmd::VarBinary& c);
                void run(const cmd::VarBinaryNoNames& c);
                void run(const cmd::VarByteswap& c);
                void run(const cmd::VarValidateAddress& c);
                void run(const cmd::VarDebug& c);
                void run(const cmd::VarSetClientTag& c);
                void run(const cmd::VarSetSendStdio& c);
                void run(const cmd::VarWriteStdio& c);
                void run(const cmd::VarServerLog& c);
                void run(const cmd::VarSendIpErrors& c);
                void run(const cmd::VarExit& c);
                void run(const cmd::SendSieResource& c);
                void run(const cmd::SendSieClass& c);
                void run(const cmd::SendSieEnum& c);
                void run(const cmd::SendSieTopLevelObjects& c);
                void run(const cmd::SendFile& c);
                void run(const cmd::VarSet& c);
                void run(const cmd::Fallback& c);

                // Variable list
                ListEntry make_entry(const std::string& name);
                std::unique_ptr<ResolvedVar> resolve(const std::string& name);
                void set_list(std::vector<ListEntry> entries);
                void set_units(std::vector<ListEntry>& entries, const std::string& name, const std::string& units);

                // Schedule
                void set_schedule(const Schedule& schedule, bool timing_changed);

                // Copies and writes
                void sample(Snapshot& out, const std::vector<ResolvedVar*>& vars, const Clock& clock, bool shared);
                void send_values(const Snapshot& snapshot, const VariableList& list, MessageType type);
                void send_vars(const std::vector<ResolvedVar*>& vars, const std::vector<ListEntry>* entries,
                               MessageType type);
                void send_frame();
                void main_copy(const Schedule& schedule);
                bool send(std::string_view message);
                void collect_notes(const std::vector<ResolvedVar*>& vars);

                // Files
                void start_file(const std::string& path);

                // Logs
                std::string prefix() const;
                void log_error(const std::string& text);
                void log_debug(int level, const std::string& text);
                void log_session(const std::string& text);
                void publish_info();

                SessionHost& _host;
                Resolver& _resolver;
                UnitConverter& _units;
                const Clock& _runner_clock;
                const Clock& _main_clock;
                SessionOutput& _output;
                const SessionConfig _config;

                // Runner thread
                std::shared_ptr<const VariableList> _list;
                uint64_t _list_versions = 0;
                Schedule _schedule;
                bool _binary       = false;
                bool _nonames      = false;
                bool _byteswap     = false;
                bool _send_stdio   = false;
                bool _ip_errors    = false;
                int _debug         = 0;
                std::string _tag;
                Snapshot _async_snapshot;
                Packets _packets;
                bool _frame_unsent = false;
                /** A file being sent, and the commands that wait for it. */
                std::unique_ptr<std::FILE, int (*)(std::FILE*)> _file { nullptr, &std::fclose };
                std::deque<Command> _waiting;
                bool _draining     = false;
                std::size_t _insert_at = 0; ///< where a command deferred while draining goes
                /** stderr text captured while Python runs a line, for the error log. */
                bool _capturing    = false;
                std::string _captured;

                // Shared with the main thread
                std::shared_ptr<const VariableList> _published_list;
                std::shared_ptr<const Schedule> _published_schedule;
                std::atomic<uint64_t> _timing_generation { 0 };
                std::shared_ptr<const Info> _published_info;
                std::mutex _stage_mutex;
                TripleBuffer<Frame> _frames;
                std::function<void()> _waker;
                std::atomic<bool> _exit { false };
                std::atomic<bool> _validate { false }; ///< var_validate_address; the main thread stages too
                std::atomic<bool> _log { false };
                std::atomic<bool> _session_log { false };

                // Main thread
                uint64_t _main_generation = 0;
                long long _next_tics        = never_tics;
                long long _freeze_next_tics = never_tics;
        };

    } // namespace vs
} // namespace Trick

#endif
