#include "trick/vs/SessionRegistry.hh"

#include <algorithm>

namespace Trick
{
    namespace vs
    {

        SessionRegistry::SessionRegistry()
            : _published(std::make_shared<const List>())
        {
        }

        void SessionRegistry::add(std::shared_ptr<Session> session)
        {
            std::lock_guard<std::mutex> guard(_mutex);
            auto next = std::make_shared<List>(*_published);
            next->push_back(std::move(session));
            std::atomic_store(&_published, std::shared_ptr<const List>(std::move(next)));
        }

        void SessionRegistry::remove(const Session* session)
        {
            std::lock_guard<std::mutex> guard(_mutex);
            auto next = std::make_shared<List>(*_published);
            const auto it = std::find_if(next->begin(), next->end(),
                                         [session](const std::shared_ptr<Session>& s) { return s.get() == session; });
            if (it == next->end())
                return;
            next->erase(it);
            std::atomic_store(&_published, std::shared_ptr<const List>(std::move(next)));
        }

        std::shared_ptr<const SessionRegistry::List> SessionRegistry::sessions() const
        {
            return std::atomic_load(&_published);
        }

        SessionRegistry::JobTimes SessionRegistry::job_times() const
        {
            JobTimes t;
            // Hold the vector: a range-for over *sessions() would drop the temporary
            // shared_ptr at once, and a runner's remove() could free the vector mid-loop.
            const auto list = sessions();
            for (const auto& s : *list)
            {
                t.next_tics        = std::min(t.next_tics, s->next_tics());
                t.freeze_next_tics = std::min(t.freeze_next_tics, s->freeze_next_tics());
            }
            return t;
        }

        SessionRegistry::JobTimes SessionRegistry::refresh(long long time_tics, long long freeze_time_tics, bool force)
        {
            // Hold the vector: a range-for over *sessions() would drop the temporary
            // shared_ptr at once, and a runner's remove() could free the vector mid-loop.
            const auto list = sessions();
            for (const auto& s : *list)
                s->main_refresh(time_tics, freeze_time_tics, force);
            return job_times();
        }

        long long SessionRegistry::copy_scheduled(long long curr_tics)
        {
            long long next = never_tics;
            // Hold the vector: a range-for over *sessions() would drop the temporary
            // shared_ptr at once, and a runner's remove() could free the vector mid-loop.
            const auto list = sessions();
            for (const auto& s : *list)
            {
                s->main_copy_scheduled(curr_tics);
                next = std::min(next, s->next_tics());
            }
            return next;
        }

        long long SessionRegistry::copy_freeze_scheduled(long long curr_tics)
        {
            long long next = never_tics;
            // Hold the vector: a range-for over *sessions() would drop the temporary
            // shared_ptr at once, and a runner's remove() could free the vector mid-loop.
            const auto list = sessions();
            for (const auto& s : *list)
            {
                s->main_copy_freeze_scheduled(curr_tics);
                next = std::min(next, s->freeze_next_tics());
            }
            return next;
        }

        void SessionRegistry::copy_top(long long frame)
        {
            // Hold the vector: a range-for over *sessions() would drop the temporary
            // shared_ptr at once, and a runner's remove() could free the vector mid-loop.
            const auto list = sessions();
            for (const auto& s : *list)
                s->main_copy_top(frame);
        }

        void SessionRegistry::copy_freeze(long long freeze_frame)
        {
            // Hold the vector: a range-for over *sessions() would drop the temporary
            // shared_ptr at once, and a runner's remove() could free the vector mid-loop.
            const auto list = sessions();
            for (const auto& s : *list)
                s->main_copy_freeze(freeze_frame);
        }

        long long SessionRegistry::freeze_init()
        {
            long long next = never_tics;
            // Hold the vector: a range-for over *sessions() would drop the temporary
            // shared_ptr at once, and a runner's remove() could free the vector mid-loop.
            const auto list = sessions();
            for (const auto& s : *list)
            {
                s->main_freeze_init();
                next = std::min(next, s->freeze_next_tics());
            }
            return next;
        }

        std::string SessionRegistry::connections_json() const
        {
            const auto list = sessions();
            std::string out = "{\"variable_server_connections\":[\n";
            for (std::size_t i = 0; i < list->size(); ++i)
            {
                out += "{\n";
                out += (*list)[i]->connection_json();
                out += '}';
                if (i + 1 < list->size())
                    out += ',';
                out += '\n';
            }
            out += "]}\n";
            return out;
        }

    } // namespace vs
} // namespace Trick
