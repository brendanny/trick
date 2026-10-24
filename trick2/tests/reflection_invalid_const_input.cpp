#include "trick2/reflection.hpp"

struct Model
{
        [[= trick2::Field { 1 }]] const double value { };
};

constexpr auto fields = trick2::describe<Model>();
int main() { }
