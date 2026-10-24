#include <array>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <trick2/integrators/rk4.hpp>
#include <utility>
#include <vector>

namespace
{

    using State  = std::array<double, 2>;
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

    constexpr auto constant_derivative_result
        = trick2::rk4_step(0.0, 0.5, std::array<double, 1> { 1.0 },
                           [](double, const std::array<double, 1>&) { return std::array<double, 1> { 2.0 }; });
    static_assert(constant_derivative_result[0] == 2.0);

    bool near(double actual, double expected, double tolerance = 1e-14)
    {
        return std::abs(actual - expected) <= tolerance;
    }

    void coupled_stage_states_and_times()
    {
        const State initial { 1.0, 0.0 };
        std::vector<std::pair<double, State>> stages;
        const auto result = trick2::rk4_step(2.0, 1.0, initial,
                                             [&](double time, const State& state)
                                             {
                                                 stages.emplace_back(time, state);
                                                 return State { state[1], -state[0] };
                                             });
        CHECK((stages
               == std::vector<std::pair<double, State>> {
                   { 2.0, { 1.0, 0.0 }   },
                   { 2.5, { 1.0, -0.5 }  },
                   { 2.5, { 0.75, -0.5 } },
                   { 3.0, { 0.5, -0.75 } }
        }));
        CHECK(near(result[0], 13.0 / 24.0));
        CHECK(near(result[1], -5.0 / 6.0));
        CHECK((initial == State { 1.0, 0.0 }));
    }

    double oscillator_error(int steps)
    {
        State state { 1.0, 0.0 };
        const double step = 1.0 / static_cast<double>(steps);
        for (int i = 0; i < steps; ++i)
        {
            state = trick2::rk4_step(static_cast<double>(i) * step, step, state,
                                     [](double, const State& current) { return State { current[1], -current[0] }; });
        }
        return std::hypot(state[0] - std::cos(1.0), state[1] + std::sin(1.0));
    }

    void harmonic_oscillator_has_fourth_order_convergence()
    {
        const double coarse = oscillator_error(8);
        const double medium = oscillator_error(16);
        const double fine   = oscillator_error(32);
        CHECK(fine < 1e-8);
        CHECK(fine > 0.0);
        CHECK(medium > fine);
        CHECK(coarse > medium);
        CHECK(coarse / medium > 14.0 && coarse / medium < 18.0);
        CHECK(medium / fine > 14.0 && medium / fine < 18.0);
    }

    void time_dependent_equation_and_signed_steps()
    {
        using Scalar    = std::array<double, 1>;
        auto derivative = [](double time, const Scalar&)
        {
            return Scalar { time };
        };
        const auto forward = trick2::rk4_step(2.0, 0.5, Scalar { 0.0 }, derivative);
        CHECK(near(forward[0], 1.125));
        const auto backward = trick2::rk4_step(1.0, -0.5, Scalar { 0.0 }, derivative);
        CHECK(near(backward[0], -0.375));
        const auto unchanged = trick2::rk4_step(1.0, 0.0, Scalar { 3.0 }, derivative);
        CHECK(unchanged[0] == 3.0);
    }

    void derivative_failure_preserves_input()
    {
        const State initial { 3.0, 4.0 };
        int calls = 0;
        CHECK_THROWS(std::runtime_error,
                     trick2::rk4_step(0.0, 0.1, initial,
                                      [&](double, const State& state)
                                      {
                                          if (++calls == 3)
                                          {
                                              throw std::runtime_error("derivative failure");
                                          }
                                          return State { state[1], -state[0] };
                                      }));
        CHECK(calls == 3);
        CHECK((initial == State { 3.0, 4.0 }));
    }

    void invalid_times_are_rejected_before_evaluation()
    {
        const auto nan      = std::numeric_limits<double>::quiet_NaN();
        const auto infinity = std::numeric_limits<double>::infinity();
        const auto largest  = std::numeric_limits<double>::max();
        int calls           = 0;
        auto derivative     = [&](double, const State&)
        {
            ++calls;
            return State { };
        };
        CHECK_THROWS(std::invalid_argument, trick2::rk4_step(nan, 1.0, State { }, derivative));
        CHECK_THROWS(std::invalid_argument, trick2::rk4_step(0.0, nan, State { }, derivative));
        CHECK_THROWS(std::invalid_argument, trick2::rk4_step(infinity, 1.0, State { }, derivative));
        CHECK_THROWS(std::invalid_argument, trick2::rk4_step(0.0, infinity, State { }, derivative));
        CHECK_THROWS(std::invalid_argument, trick2::rk4_step(largest, largest, State { }, derivative));
        CHECK(calls == 0);
    }

} // namespace

int main()
{
    try
    {
        coupled_stage_states_and_times();
        harmonic_oscillator_has_fourth_order_convergence();
        time_dependent_equation_and_signed_steps();
        derivative_failure_preserves_input();
        invalid_times_are_rejected_before_evaluation();
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
        std::cerr << failures << " RK4 checks failed\n";
        return 1;
    }
    std::cout << "RK4 tests passed\n";
}
