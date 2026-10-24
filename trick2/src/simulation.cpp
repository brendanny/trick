#include <limits>
#include <stdexcept>
#include <trick2/simulation.hpp>
#include <utility>

namespace trick2
{

    void Simulation::require_ready() const
    {
        switch (state_)
        {
        case State::ready:
            return;
        case State::running:
            throw std::logic_error("simulation is already running");
        case State::stopped:
            throw std::logic_error("simulation has stopped");
        case State::failed:
            throw std::logic_error("simulation has failed");
        }
        throw std::logic_error("invalid simulation state");
    }

    job_id Simulation::every(Duration period, Phase phase, Job job, std::string name)
    {
        require_ready();
        if (period <= Duration::zero())
        {
            throw std::invalid_argument("job period must be positive");
        }
        switch (phase)
        {
        case Phase::input:
        case Phase::dynamics:
        case Phase::control:
        case Phase::observation:
            break;
        default:
            throw std::invalid_argument("invalid job phase");
        }
        if (!job)
        {
            throw std::invalid_argument("job callback must not be empty");
        }
        if (period > Duration::max() - time_)
        {
            throw std::overflow_error("first job deadline exceeds the clock range");
        }
        if (next_id_ == std::numeric_limits<job_id>::max())
        {
            throw std::overflow_error("job identifiers exhausted");
        }

        const auto id = next_id_;
        jobs_.push_back({ id, period, phase, std::move(job), std::move(name), time_ + period });
        ++next_id_;
        return id;
    }

    void Simulation::run_until(Duration horizon)
    {
        require_ready();
        if (horizon < time_)
        {
            throw std::invalid_argument("run horizon precedes the simulation time");
        }

        state_ = State::running;
        try
        {
            while (!stop_requested_)
            {
                std::optional<Duration> next_time;
                for (const auto& job : jobs_)
                {
                    if (job.next && (!next_time || *job.next < *next_time))
                    {
                        next_time = job.next;
                    }
                }
                if (!next_time || *next_time > horizon)
                {
                    time_ = horizon;
                    break;
                }

                time_                    = *next_time;
                constexpr Phase phases[] = { Phase::input, Phase::dynamics, Phase::control, Phase::observation };
                for (const auto phase : phases)
                {
                    // jobs_ stays in registration order and cannot change while running.
                    for (auto& job : jobs_)
                    {
                        if (job.phase != phase || job.next != next_time)
                        {
                            continue;
                        }

                        job.callback(StepContext { time_, job.period });
                        if (job.period > Duration::max() - time_)
                        {
                            // No legal future horizon can reach this next deadline.
                            job.next.reset();
                        }
                        else
                        {
                            job.next = time_ + job.period;
                        }
                        if (stop_requested_)
                        {
                            break;
                        }
                    }
                    if (stop_requested_)
                    {
                        break;
                    }
                }
            }
        }
        catch (...)
        {
            state_ = State::failed;
            throw;
        }
        state_ = stop_requested_ ? State::stopped : State::ready;
    }

    void Simulation::request_stop() noexcept
    {
        if (state_ == State::ready)
        {
            state_ = State::stopped;
        }
        else if (state_ == State::running)
        {
            stop_requested_ = true;
        }
    }

} // namespace trick2
