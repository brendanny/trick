#include "trick2/reflection.hpp"

struct Model
{
        [[= trick2::Field { 1 }]] int value { };
};

constexpr auto fields = trick2::describe<Model>();
int main() { }
