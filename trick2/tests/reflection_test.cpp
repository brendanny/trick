#include "trick2/reflection.hpp"

#include <cstdlib>
#include <iostream>

namespace
{

    struct Sample
    {
            [[= trick2::Field { 7, trick2::Unit::metre }]] double position { 2.0 };

            [[= trick2::Field { 19, trick2::Unit::metre_per_second }]] double velocity { -0.5 };

            [[= trick2::Field { 31, trick2::Unit::radian_per_second,
                                trick2::Access::output }]] const double rate { 4.0 };

            void reset() { position = 0.0; }
            static constexpr double implementation_constant = 123.0;
    };

    struct Empty
    {
    };

    constexpr auto fields = trick2::describe<Sample>();
    static_assert(fields.size() == 3);
    static_assert(fields[0].id == 7 && fields[0].name == "position");
    static_assert(fields[0].unit == trick2::Unit::metre);
    static_assert(fields[1].id == 19 && fields[1].name == "velocity");
    static_assert(fields[2].id == 31 && fields[2].name == "rate");
    static_assert(fields[2].write == nullptr);
    static_assert(trick2::describe<Empty>().empty());

    void require(bool condition, const char* message)
    {
        if (!condition)
        {
            std::cerr << message << '\n';
            std::exit(EXIT_FAILURE);
        }
    }

} // namespace

int main()
{
    Sample first;
    Sample second;
    require(fields[0].read(&first) == 2.0, "read the first instance's member");
    require(fields[1].read(&first) == -0.5, "read a second reflected member");
    fields[0].write(&first, 12.0);
    require(first.position == 12.0, "write reaches the typed member");
    require(second.position == 2.0, "descriptors are reusable across instances");
    require(fields[2].read(&first) == 4.0, "const members remain readable");
    require(trick2::has_access(fields[2].access, trick2::Access::output),
            "annotation access policy reaches runtime metadata");
    require(!trick2::has_access(fields[2].access, trick2::Access::input), "const output is not exposed as input");
}
