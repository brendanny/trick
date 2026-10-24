#include "trick2/reflection.hpp"

struct Base
{
        [[= trick2::Field { 1 }]] double value { };
};

struct Model : Base
{
};

constexpr auto fields = trick2::describe<Model>();
int main() { }
