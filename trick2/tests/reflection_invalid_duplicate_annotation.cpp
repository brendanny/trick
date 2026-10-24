#include "trick2/reflection.hpp"

struct Model
{
        [[ = trick2::Field { 1 }, = trick2::Field { 2 } ]] double value { };
};

constexpr auto fields = trick2::describe<Model>();
int main() { }
