#include <iostream>
#include <stdexcept>
#include <string>
#include <trick2/simulation.hpp>
#include <utility>
#include <vector>

namespace
{

    using namespace std::chrono_literals;
    using trick2::Duration;
    using trick2::Phase;
    using trick2::Simulation;
    using trick2::StepContext;

    int failures = 0;

    void check(bool condition, const char* expression, int line)
    {
        if (!condition)
        {
            std::cerr << "line " << line << ": check failed: " << expression << '\n';
            ++failures;
        }
    }

#define CHECK(condition) check((condition), #condition, __LINE__)

    template <class Exception, class Function> void check_throws(Function&& function, int line)
    {
        try
        {
            std::forward<Function>(function)();
        }
        catch (const Exception&)
        {
            return;
        }
        catch (...)
        {
            check(false, "unexpected exception type", line);
            return;
        }
        check(false, "expected an exception", line);
    }

#define CHECK_THROWS(exception, expression) check_throws<exception>([&] { (void)(expression); }, __LINE__)

    void ordering_and_first_firing()
    {
        Simulation sim;
        std::vector<std::string> calls;
        auto callback = [&](std::string label)
        {
            return [&, label = std::move(label)](const StepContext& context)
            {
                CHECK(context.time == 10ns);
                CHECK(context.step == 10ns);
                CHECK(sim.time() == context.time);
                calls.push_back(label);
            };
        };

        const auto first  = sim.every(10ns, Phase::control, callback("control"));
        const auto second = sim.every(10ns, Phase::input, callback("input A"));
        (void)sim.every(10ns, Phase::observation, callback("observation"));
        (void)sim.every(10ns, Phase::dynamics, callback("dynamics"));
        (void)sim.every(10ns, Phase::input, callback("input B"));
        CHECK(second > first);

        sim.run_until(0ns);
        sim.run_until(9ns);
        CHECK(calls.empty());
        CHECK(sim.time() == 9ns);
        sim.run_until(10ns);
        CHECK((calls == std::vector<std::string> { "input A", "input B", "dynamics", "control", "observation" }));
        CHECK(!sim.stopped());
        CHECK(!sim.failed());
    }

    void continuation_and_mixed_periods()
    {
        Simulation sim;
        std::vector<std::pair<char, Duration>> calls;
        (void)sim.every(2ns, Phase::dynamics,
                        [&](const StepContext& context)
                        {
                            CHECK(context.step == 2ns);
                            calls.emplace_back('A', context.time);
                        });
        (void)sim.every(3ns, Phase::input,
                        [&](const StepContext& context)
                        {
                            CHECK(context.step == 3ns);
                            calls.emplace_back('B', context.time);
                        });

        sim.run_until(4ns);
        CHECK(calls.size() == 3);
        sim.run_until(4ns);
        CHECK(calls.size() == 3);
        sim.run_until(7ns);
        CHECK(sim.time() == 7ns);
        CHECK((calls
               == std::vector<std::pair<char, Duration>> {
                   { 'A', 2ns },
                   { 'B', 3ns },
                   { 'A', 4ns },
                   { 'B', 6ns },
                   { 'A', 6ns }
        }));
    }

    void registration_after_advancing()
    {
        Simulation sim;
        sim.run_until(20ns);
        int calls = 0;
        (void)sim.every(
            5ns, Phase::input,
            [&](const StepContext& context)
            {
                CHECK(context.time == 25ns);
                CHECK(context.step == 5ns);
                ++calls;
            },
            "late registration");
        sim.run_until(24ns);
        CHECK(calls == 0);
        sim.run_until(25ns);
        CHECK(calls == 1);
    }

    void invalid_arguments_leave_simulation_ready()
    {
        Simulation sim;
        auto callback = [](const StepContext&) {};
        CHECK_THROWS(std::invalid_argument, sim.every(0ns, Phase::input, callback));
        CHECK_THROWS(std::invalid_argument, sim.every(-1ns, Phase::input, callback));
        CHECK_THROWS(std::invalid_argument, sim.every(1ns, Phase::input, { }));
        CHECK_THROWS(std::invalid_argument, sim.every(1ns, static_cast<Phase>(42), callback));
        CHECK_THROWS(std::invalid_argument, sim.run_until(-1ns));
        sim.run_until(10ns);
        CHECK_THROWS(std::invalid_argument, sim.run_until(9ns));
        CHECK(sim.time() == 10ns);
        CHECK(!sim.failed());
        CHECK(!sim.stopped());
        CHECK(sim.every(1ns, Phase::input, callback) == 1);
        sim.run_until(11ns);
    }

    void reentrant_calls_and_registration_are_rejected()
    {
        Simulation sim;
        int calls = 0;
        (void)sim.every(1ns, Phase::input,
                        [&](const StepContext& context)
                        {
                            CHECK_THROWS(std::logic_error, sim.run_until(context.time));
                            CHECK_THROWS(std::logic_error, sim.every(1ns, Phase::input, [](const StepContext&) { }));
                            ++calls;
                        });
        sim.run_until(2ns);
        CHECK(calls == 2);
        CHECK(!sim.failed());
    }

    void stop_is_terminal_and_preserves_current_time()
    {
        Simulation sim;
        int first_calls = 0;
        int later_calls = 0;
        (void)sim.every(3ns, Phase::input,
                        [&](const StepContext&)
                        {
                            ++first_calls;
                            sim.request_stop();
                        });
        (void)sim.every(3ns, Phase::input, [&](const StepContext&) { ++later_calls; });
        sim.run_until(20ns);
        CHECK(first_calls == 1);
        CHECK(later_calls == 0);
        CHECK(sim.time() == 3ns);
        CHECK(sim.stopped());
        CHECK(!sim.failed());
        CHECK_THROWS(std::logic_error, sim.run_until(20ns));
        CHECK_THROWS(std::logic_error, sim.every(1ns, Phase::input, [](const StepContext&) { }));

        Simulation never_started;
        never_started.request_stop();
        CHECK(never_started.stopped());
        CHECK(never_started.time() == 0ns);
        CHECK_THROWS(std::logic_error, never_started.run_until(0ns));
    }

    void callback_failure_cannot_replay_a_partial_timestamp()
    {
        Simulation sim;
        int completed = 0;
        int skipped   = 0;
        (void)sim.every(5ns, Phase::input, [&](const StepContext&) { ++completed; });
        (void)sim.every(5ns, Phase::control, [](const StepContext&) { throw std::runtime_error("model failure"); });
        (void)sim.every(5ns, Phase::observation, [&](const StepContext&) { ++skipped; });
        try
        {
            sim.run_until(10ns);
            CHECK(false);
        }
        catch (const std::runtime_error& error)
        {
            CHECK(std::string(error.what()) == "model failure");
        }
        CHECK(completed == 1);
        CHECK(skipped == 0);
        CHECK(sim.time() == 5ns);
        CHECK(sim.failed());
        CHECK(!sim.stopped());
        sim.request_stop();
        CHECK(sim.failed());
        CHECK(!sim.stopped());
        CHECK_THROWS(std::logic_error, sim.run_until(5ns));
        CHECK_THROWS(std::logic_error, sim.every(1ns, Phase::input, [](const StepContext&) { }));
        CHECK(completed == 1);
    }

    void clock_limits_do_not_wrap()
    {
        Simulation sim;
        const auto limit = Duration::max();
        sim.run_until(limit - 2ns);
        int calls = 0;
        CHECK_THROWS(std::overflow_error, sim.every(3ns, Phase::input, [](const StepContext&) { }));
        CHECK(sim.every(1ns, Phase::input,
                        [&](const StepContext& context)
                        {
                            ++calls;
                            CHECK(context.time == limit - (calls == 1 ? 1ns : 0ns));
                        })
              == 1);
        sim.run_until(limit);
        CHECK(calls == 2);
        CHECK(sim.time() == limit);
        CHECK(!sim.failed());
        sim.run_until(limit);
        CHECK(calls == 2);
        CHECK_THROWS(std::overflow_error, sim.every(1ns, Phase::input, [](const StepContext&) { }));

        Simulation full_range;
        int last_calls = 0;
        (void)full_range.every(limit, Phase::input, [&](const StepContext&) { ++last_calls; });
        full_range.run_until(limit);
        full_range.run_until(limit);
        CHECK(last_calls == 1);
        CHECK(!full_range.failed());
    }

} // namespace

int main()
{
    try
    {
        ordering_and_first_firing();
        continuation_and_mixed_periods();
        registration_after_advancing();
        invalid_arguments_leave_simulation_ready();
        reentrant_calls_and_registration_are_rejected();
        stop_is_terminal_and_preserves_current_time();
        callback_failure_cannot_replay_a_partial_timestamp();
        clock_limits_do_not_wrap();
    }
    catch (const std::exception& error)
    {
        std::cerr << "unexpected exception: " << error.what() << '\n';
        return 1;
    }
    catch (...)
    {
        std::cerr << "unexpected non-standard exception\n";
        return 1;
    }
    if (failures != 0)
    {
        std::cerr << failures << " simulation checks failed\n";
        return 1;
    }
    std::cout << "simulation tests passed\n";
}
