/*
PURPOSE: (The sessions of a variable server, and the work the simulation jobs do on them.)

A mutex guards only add() and remove(). Each change publishes a new
immutable vector, and the jobs on the main thread read the published vector
with std::atomic_load, so a job never waits for a session to be added or
removed, and never holds a lock while it copies values.

The job functions return the times the executive should call the
scheduled jobs next: the smallest next_tics (or freeze_next_tics) of any
session, or never_tics.
*/

#ifndef TRICK_VS_SESSIONREGISTRY_HH
#define TRICK_VS_SESSIONREGISTRY_HH

#include "trick/vs/Session.hh"

#include <memory>
#include <mutex>
#include <string>
#include <vector>

namespace Trick
{
    namespace vs
    {

        class SessionRegistry
        {
            public:
                using List = std::vector<std::shared_ptr<Session>>;

                SessionRegistry();

                void add(std::shared_ptr<Session> session);

                /** Remove a session. Does nothing if it is not registered. */
                void remove(const Session* session);

                /** The sessions now. The vector never changes; a change publishes a new one. */
                std::shared_ptr<const List> sessions() const;

                std::size_t size() const { return sessions()->size(); }

                // -------------------------------------------------- main thread (jobs)

                struct JobTimes
                {
                        long long next_tics        = never_tics;
                        long long freeze_next_tics = never_tics;
                };

                /**
                 * Apply the timing changes of every session; return the new job times. `force`
                 * recomputes every scheduled session from `time_tics` (after a checkpoint load
                 * moved sim time, a time from before the load would never come).
                 */
                JobTimes refresh(long long time_tics, long long freeze_time_tics, bool force = false);

                /** copy_and_write_scheduled at `curr_tics`. Returns the next call time. */
                long long copy_scheduled(long long curr_tics);

                /** copy_and_write_freeze_scheduled at `curr_tics`. Returns the next call time. */
                long long copy_freeze_scheduled(long long curr_tics);

                /** copy_and_write_top for `frame`. */
                void copy_top(long long frame);

                /** copy_and_write_freeze for `freeze_frame`. */
                void copy_freeze(long long freeze_frame);

                /** freeze_init. Returns the next freeze call time. */
                long long freeze_init();

                /** The smallest next_tics and freeze_next_tics now. */
                JobTimes job_times() const;

                // -------------------------------------------------------- any thread

                /** The connection list as the old server wrote it: {"variable_server_connections":[...]}. */
                std::string connections_json() const;

            private:
                mutable std::mutex _mutex;
                std::shared_ptr<const List> _published;
        };

    } // namespace vs
} // namespace Trick

#endif
