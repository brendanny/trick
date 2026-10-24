#include "model.hpp"

namespace legacy
{

    std::array<double, 2> Oscillator::derivatives(const std::array<double, 2>& state) const noexcept
    {
        return { state[1], -angular_frequency * angular_frequency * state[0] };
    }

} // namespace legacy
