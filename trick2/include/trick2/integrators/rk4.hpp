#pragma once

#include <array>
#include <concepts>
#include <cstddef>
#include <functional>
#include <limits>
#include <stdexcept>
#include <type_traits>

namespace trick2
{

    namespace detail
    {

        constexpr bool rk4_is_finite(double value) noexcept
        {
            constexpr auto largest = std::numeric_limits<double>::max();
            return value >= -largest && value <= largest;
        }

    } // namespace detail

    // One classical Runge-Kutta step for a coupled state. Each derivative evaluation
    // sees the complete state of that stage; the input state is never modified.
    // A finite positive, negative, or zero step is accepted. Numerical error control,
    // event detection, and validation of model outputs belong to the caller.
    template <std::size_t N, class Derivative>
        requires std::invocable<Derivative&, double, const std::array<double, N>&>
        && std::same_as<std::invoke_result_t<Derivative&, double, const std::array<double, N>&>, std::array<double, N>>
    [[nodiscard]] constexpr std::array<double, N> rk4_step(double time, double step, const std::array<double, N>& state,
                                                           Derivative&& derivative)
    {
        if (!detail::rk4_is_finite(time) || !detail::rk4_is_finite(step) || !detail::rk4_is_finite(time + step))
        {
            throw std::invalid_argument("RK4 requires finite time, step, and end time");
        }

        const double half_step = step / 2.0;
        const auto k1          = std::invoke(derivative, time, state);
        std::array<double, N> stage { };
        for (std::size_t i = 0; i < N; ++i)
        {
            stage[i] = state[i] + half_step * k1[i];
        }
        const auto k2 = std::invoke(derivative, time + half_step, static_cast<const std::array<double, N>&>(stage));
        for (std::size_t i = 0; i < N; ++i)
        {
            stage[i] = state[i] + half_step * k2[i];
        }
        const auto k3 = std::invoke(derivative, time + half_step, static_cast<const std::array<double, N>&>(stage));
        for (std::size_t i = 0; i < N; ++i)
        {
            stage[i] = state[i] + step * k3[i];
        }
        const auto k4 = std::invoke(derivative, time + step, static_cast<const std::array<double, N>&>(stage));

        std::array<double, N> result { };
        for (std::size_t i = 0; i < N; ++i)
        {
            result[i] = state[i] + (step / 6.0) * (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i]);
        }
        return result;
    }

} // namespace trick2
