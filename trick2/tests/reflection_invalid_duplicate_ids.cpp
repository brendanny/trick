#include "trick2/reflection.hpp"

struct Model
{
        [[= trick2::Field { 7 }]] double first { };
        [[= trick2::Field { 7 }]] double second { };
};

constexpr auto fields = trick2::describe<Model>();
int main() { }
