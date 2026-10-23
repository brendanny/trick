#include "trick/vs/SessionRunner.hh"

#include "trick/vs/CLocale.hh"

#include <algorithm>
#include <vector>

namespace Trick
{
    namespace vs
    {

        RunnerHooks::~RunnerHooks() = default;

        void RunnerHooks::run(Session&, const std::function<void()>& work) { work(); }

        void RunnerHooks::started(Session&) {}

        void RunnerHooks::finished(Session&) {}

        void RunnerHooks::log(Session&, const std::string&, bool) {}

        namespace
        {
            /** Runners whose thread did not stop. Kept until the process exits, never destroyed. */
            std::mutex& abandoned_mutex()
            {
                static std::mutex* m = new std::mutex;
                return *m;
            }

            std::vector<std::shared_ptr<SessionRunner>>& abandoned()
            {
                static auto* v = new std::vector<std::shared_ptr<SessionRunner>>;
                return *v;
            }
        } // namespace

        Expected<std::shared_ptr<SessionRunner>> SessionRunner::create(std::unique_ptr<Connection> connection,
                                                                        const SessionMaker& make, RunnerHooks& hooks,
                                                                        std::shared_ptr<void> keep_alive)
        {
            auto poller = Poller::create();
            if (!poller)
                return poller.error();
            std::shared_ptr<SessionRunner> runner(new SessionRunner(
                std::move(connection), std::make_shared<Poller>(std::move(poller.value())), hooks, std::move(keep_alive)));
            runner->_session = make(*runner);
            if (!runner->_session)
                return Error { "the session could not be made" };
            std::shared_ptr<Poller> wake = runner->_poller;
            runner->_session->set_waker([wake] { wake->wake(); });
            return runner;
        }

        SessionRunner::~SessionRunner()
        {
            if (_thread.joinable())
            {
                // Only an abandoned runner has a running thread, and it is never destroyed.
                stop();
                _thread.join();
            }
        }

        std::size_t SessionRunner::file_chunk() const
        {
            // One datagram per chunk for UDP and multicast, as the old server sent files.
            return _connection->kind() == ConnectionKind::Tcp ? 65536 : 4095;
        }

        void SessionRunner::start()
        {
            {
                std::lock_guard<std::mutex> guard(_finished_mutex);
                _finished = false;
            }
            _thread = std::thread([this] { body(); });
        }

        void SessionRunner::stop() noexcept
        {
            _stop.store(true, std::memory_order_release);
            _poller->wake();
        }

        bool SessionRunner::finished() const
        {
            std::lock_guard<std::mutex> guard(_finished_mutex);
            return _finished;
        }

        bool SessionRunner::wait_until(std::chrono::steady_clock::time_point deadline) const
        {
            std::unique_lock<std::mutex> lock(_finished_mutex);
            return _finished_cv.wait_until(lock, deadline, [this] { return _finished; });
        }

        void SessionRunner::join()
        {
            if (_thread.joinable())
                _thread.join();
        }

        void SessionRunner::abandon(std::shared_ptr<SessionRunner> self)
        {
            if (self->_thread.joinable())
                self->_thread.detach();
            std::lock_guard<std::mutex> guard(abandoned_mutex());
            abandoned().push_back(std::move(self));
        }

        void SessionRunner::mark_finished()
        {
            std::lock_guard<std::mutex> guard(_finished_mutex);
            _finished = true;
            _finished_cv.notify_all();
        }

        void SessionRunner::read_all()
        {
            Session& session = *_session;
            while (!session.exiting() && !session.busy())
            {
                ReadResult r = _connection->read(_batch);
                if (!r.note.empty())
                    _hooks.log(session, r.note, r.status == ReadResult::Status::Error);
                switch (r.status)
                {
                    case ReadResult::Status::Batch:
                        _hooks.run(session, [&] { session.handle_batch(_batch); });
                        break;
                    case ReadResult::Status::Nothing:
                        return;
                    case ReadResult::Status::Closed:
                    case ReadResult::Status::Error:
                        session.request_exit();
                        return;
                }
            }
        }

        void SessionRunner::body()
        {
            using clock = std::chrono::steady_clock;
            ScopedCLocale c_locale;
            Session& session = *_session;
            _hooks.started(session);
            session.start();

            std::vector<pollfd> items(1);
            clock::time_point next = clock::now();
            while (!_stop.load(std::memory_order_acquire) && !session.exiting())
            {
                const auto wait = std::chrono::duration_cast<std::chrono::milliseconds>(next - clock::now()).count();
                const int timeout = static_cast<int>(std::max<long long>(0, std::min<long long>(wait + 1, 1000)));

                items[0].fd     = _connection->fd();
                items[0].events = static_cast<short>((session.busy() ? 0 : POLLIN) | (_connection->wants_write() ? POLLOUT : 0));
                auto woken = _poller->wait(items, timeout);
                if (!woken)
                {
                    _hooks.log(session, "variable server session: " + woken.error().message, true);
                    break;
                }
                if (_stop.load(std::memory_order_acquire))
                    break;
                if (woken.value())
                    _hooks.run(session, [&] { session.on_wake(); });
                if ((items[0].revents & (POLLIN | POLLHUP | POLLERR | POLLNVAL)) != 0)
                    read_all();

                const clock::time_point now = clock::now();
                if (now >= next)
                {
                    _hooks.run(session, [&] { session.on_deadline(); });
                    const auto period = std::chrono::duration_cast<clock::duration>(
                        std::chrono::duration<double>(std::max(session.cycle_s(), 1e-6)));
                    next += period;
                    if (next <= now)
                        next = now + period;
                }

                if (session.busy())
                    _hooks.run(session, [&] { session.continue_file(); });
                if (_connection->wants_write())
                {
                    const FlushResult f = _connection->flush();
                    if (f.status == FlushResult::Status::Error)
                    {
                        // A client that leaves in the middle of a reply is not an error.
                        if (!f.note.empty())
                            _hooks.log(session, f.note, !f.client_closed);
                        session.request_exit();
                    }
                }
            }

            // Send what is queued if the socket takes it now (var_exit after a reply).
            if (_connection->is_open() && _connection->wants_write())
                _connection->flush();
            _connection->close();
            _hooks.finished(session);
            mark_finished();
        }

    } // namespace vs
} // namespace Trick
