/*
PURPOSE: (The thread that owns one Session and its Connection.)

One runner per client: a TCP client the listener accepted, or a UDP or
multicast socket (var_server_create_udp_socket and
var_server_create_multicast_socket). The runner polls its socket and its
wake pipe, with the next asynchronous deadline (var_cycle) as the timeout.
It runs commands when they arrive, not once per cycle as the old session
thread did. It is the only thread that sends to its client: the main
thread copies values and wakes it.

The runner never holds a lock during I/O or Python, and nothing cancels it:
stop() sets a flag and wakes it. A runner that does not stop (it is inside
a Python call that does not return) can be abandoned: its thread is
detached and the runner is kept until the process exits, so the thread
never uses freed memory.
*/

#ifndef TRICK_VS_SESSIONRUNNER_HH
#define TRICK_VS_SESSIONRUNNER_HH

#include "trick/vs/Connection.hh"
#include "trick/vs/Expected.hh"
#include "trick/vs/Poller.hh"
#include "trick/vs/Session.hh"

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <thread>

namespace Trick
{
    namespace vs
    {

        /** What the owner of a runner does around its work. The adapter sets the current session for Python. */
        class RunnerHooks
        {
            public:
                virtual ~RunnerHooks();

                /** Run `work` (commands, or a copy) for `session` on the runner thread. */
                virtual void run(Session& session, const std::function<void()>& work);

                /** The runner thread started, before the session starts. */
                virtual void started(Session& session);

                /** The runner thread is about to end; the connection is closed. */
                virtual void finished(Session& session);

                /** A socket problem, for the message system. */
                virtual void log(Session& session, const std::string& text, bool error);
        };

        class SessionRunner final : public SessionOutput
        {
            public:
                using SessionMaker = std::function<std::shared_ptr<Session>(SessionOutput& output)>;

                /**
                 * Make a runner for `connection`. `make` builds the Session that sends through
                 * the runner. `keep_alive` is held until the runner is destroyed (the server
                 * the session's references point into). The thread starts in start().
                 */
                static Expected<std::shared_ptr<SessionRunner>> create(std::unique_ptr<Connection> connection,
                                                                       const SessionMaker& make, RunnerHooks& hooks,
                                                                       std::shared_ptr<void> keep_alive = nullptr);

                ~SessionRunner() override;

                SessionRunner(const SessionRunner&)            = delete;
                SessionRunner& operator=(const SessionRunner&) = delete;

                /** Start the thread. */
                void start();

                /** Ask the thread to end (any thread). */
                void stop() noexcept;

                /** True when the thread has ended (or never started). */
                bool finished() const;

                /** Wait until the thread ends or `deadline` passes. True if it ended. */
                bool wait_until(std::chrono::steady_clock::time_point deadline) const;

                /** Join the thread if it ended. Call only after finished() is true. */
                void join();

                /**
                 * Give up on a thread that did not end: detach it and keep this runner until
                 * the process exits. `self` must own this runner.
                 */
                static void abandon(std::shared_ptr<SessionRunner> self);

                const std::shared_ptr<Session>& session() const noexcept { return _session; }

                const Connection& connection() const noexcept { return *_connection; }

                /** Wake the runner (any thread). */
                void wake() const noexcept { _poller->wake(); }

                // SessionOutput (runner thread)
                bool send(std::string_view message) override { return _connection->send(message); }
                std::size_t space() const override { return _connection->queue().space(); }
                std::size_t file_chunk() const override;

            private:
                SessionRunner(std::unique_ptr<Connection> connection, std::shared_ptr<Poller> poller, RunnerHooks& hooks,
                              std::shared_ptr<void> keep_alive)
                    : _connection(std::move(connection))
                    , _poller(std::move(poller))
                    , _hooks(hooks)
                    , _keep_alive(std::move(keep_alive))
                {
                }

                void body();
                void read_all();
                void mark_finished();

                std::unique_ptr<Connection> _connection;
                std::shared_ptr<Poller> _poller;
                RunnerHooks& _hooks;
                std::shared_ptr<void> _keep_alive;
                std::shared_ptr<Session> _session;
                std::thread _thread;
                std::atomic<bool> _stop { false };
                mutable std::mutex _finished_mutex;
                mutable std::condition_variable _finished_cv;
                bool _finished = true;
                std::string _batch;
        };

    } // namespace vs
} // namespace Trick

#endif
