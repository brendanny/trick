#pragma once

#include <chrono>
#include <cstdint>
#include <functional>
#include <optional>
#include <string>
#include <vector>

namespace trick2
{

    using Duration = std::chrono::nanoseconds;
    using job_id   = std::uint64_t;

    enum class Phase
    {
        input,
        dynamics,
        control,
        observation
    };

    struct StepContext
    {
            Duration time;
            Duration step;
    };

    // A serial executive with a logical clock. Calls are not thread-safe.
    class Simulation
    {
        public:
            using Job = std::function<void(const StepContext&)>;

            Simulation()                             = default;
            Simulation(const Simulation&)            = delete;
            Simulation& operator=(const Simulation&) = delete;
            Simulation(Simulation&&)                 = delete;
            Simulation& operator=(Simulation&&)      = delete;

            // The first firing is time() + period. Equal-time jobs run in phase order,
            // then registration order. A name is descriptive and does not affect order.
            // Registration is permitted only while ready, outside run_until().
            [[nodiscard]] job_id every(Duration period, Phase phase, Job job, std::string name = { });

            // Runs all deadlines at or before the absolute horizon, then advances time
            // to that horizon. A successful later call continues the existing schedule.
            // On callback failure, time() is the failing timestamp and this Simulation
            // becomes permanently failed. Already completed effects are not rolled back.
            void run_until(Duration horizon);

            [[nodiscard]] Duration time() const noexcept { return time_; }
            [[nodiscard]] bool stopped() const noexcept { return state_ == State::stopped; }
            [[nodiscard]] bool failed() const noexcept { return state_ == State::failed; }

            // Stops after the current callback, without running other jobs at its
            // timestamp. A stop requested before running takes effect immediately.
            // Stopped and failed simulations cannot be run or extended.
            void request_stop() noexcept;

        private:
            enum class State
            {
                ready,
                running,
                stopped,
                failed
            };

            struct PeriodicJob
            {
                    job_id id;
                    Duration period;
                    Phase phase;
                    Job callback;
                    std::string name;
                    // Empty when the next mathematical deadline is beyond Duration::max().
                    std::optional<Duration> next;
            };

            void require_ready() const;

            Duration time_ { };
            State state_ { State::ready };
            bool stop_requested_ { false };
            job_id next_id_ { 1 };
            std::vector<PeriodicJob> jobs_;
    };

} // namespace trick2
