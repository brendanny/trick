#include "trick2/reflection.hpp"

class Model
{
        [[= trick2::Field { 1 }]] double value { };
};

constexpr auto fields = trick2::describe<Model>();
int main() { }
