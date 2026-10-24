#pragma once

#include <array>

// This model header and its implementation are plain C++17. They include no
// Trick2 headers and carry no annotations or conditional class definitions.
namespace legacy
{

    struct Oscillator
    {
            double position { 1.0 };
            double velocity { 0.0 };
            const double angular_frequency { 1.0 };

            std::array<double, 2> derivatives(const std::array<double, 2>& state) const noexcept;
    };

} // namespace legacy
