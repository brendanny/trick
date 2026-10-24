#include "trick2/reflection.hpp"

struct Model
{
        double value { };
};

constexpr auto fields = trick2::describe<Model>();
int main() { }
