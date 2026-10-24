#pragma once

#include "trick2/schema.hpp"

namespace example
{

    struct Model
    {
            [[= trick2::Field { 1, trick2::Unit::metre }]] double position { 1.0 };

            [[= trick2::Field { 2, trick2::Unit::metre_per_second }]] double velocity { 0.0 };

            [[= trick2::Field { 3, trick2::Unit::radian_per_second,
                                trick2::Access::output }]] const double angular_frequency { 1.0 };

            void advance(double time, double step);
    };

    trick2::TypeDescriptor model_schema() noexcept;

} // namespace example
