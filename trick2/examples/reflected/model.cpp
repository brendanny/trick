#include "model.hpp"

#include "trick2/integrators/rk4.hpp"

#include <array>

namespace example
{

    void Model::advance(double time, double step)
    {
        const auto next = trick2::rk4_step(
            time, step, std::array { position, velocity }, [this](double, const std::array<double, 2>& state)
            { return std::array { state[1], -angular_frequency * angular_frequency * state[0] }; });
        position = next[0];
        velocity = next[1];
    }

} // namespace example
