#include "../common/run_oscillator.hpp"
#include "model.hpp"
#include "trick2/integrators/rk4.hpp"

#include <array>
#include <exception>
#include <iostream>

namespace
{
    using Model = legacy::Oscillator;
    using trick2::Access;
    using trick2::Field;
    using trick2::Unit;

    // An explicit C++ adapter for existing models. This is not reflection and is
    // intentionally usable by the bootstrap build as well as the native build.
    constexpr std::array fields { trick2::make_field<Model, &Model::position>(Field { 1, Unit::metre }, "position"),
                                  trick2::make_field<Model, &Model::velocity>(Field { 2, Unit::metre_per_second },
                                                                              "velocity"),
                                  trick2::make_field<Model, &Model::angular_frequency>(
                                      Field { 3, Unit::radian_per_second, Access::output }, "angular_frequency") };
    constexpr trick2::TypeDescriptor schema { "Oscillator", fields };
} // namespace

int main(int argc, char** argv)
{
    try
    {
        Model oscillator;
        return example::run_oscillator(argc, argv, oscillator, schema,
                                       [](Model& model, double begin, double step)
                                       {
                                           const auto next = trick2::rk4_step(
                                               begin, step, std::array { model.position, model.velocity },
                                               [&model](double, const std::array<double, 2>& state)
                                               { return model.derivatives(state); });
                                           model.position = next[0];
                                           model.velocity = next[1];
                                       });
    }
    catch (const std::exception& error)
    {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
