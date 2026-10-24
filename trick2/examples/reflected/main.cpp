#include "../common/run_oscillator.hpp"
#include "model.hpp"

#include <exception>
#include <iostream>

int main(int argc, char** argv)
{
    try
    {
        example::Model oscillator;
        return example::run_oscillator(argc, argv, oscillator, example::model_schema(),
                                       [](example::Model& model, double time, double step)
                                       { model.advance(time, step); });
    }
    catch (const std::exception& error)
    {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
