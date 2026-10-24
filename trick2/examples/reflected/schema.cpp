#include "model.hpp"
#include "trick2/reflection.hpp"

namespace example
{
    namespace
    {

        constexpr auto fields = trick2::describe<Model>();

    } // namespace

    trick2::TypeDescriptor model_schema() noexcept { return { "Oscillator", fields }; }

} // namespace example
