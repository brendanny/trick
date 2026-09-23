#include <Python.h>

#include "trick/ExecutiveException.hh"
#include "trick/IPPython.hh"
#include "trick/MemoryManager.hh"
#include "trick/UdUnits.hh"
#include "trick/python_modules.h"

#include <cstdio>
#include <cstdlib>

extern "C" void init_swig_modules()
{
    if (trick_init_core_python_modules() != 0)
    {
        if (Py_IsInitialized())
        {
            PyErr_Print();
        }
        std::fputs("Core Python module registration failed\n", stderr);
        std::abort();
    }
}

void populate_sim_services_class_map();
void populate_sim_services_enum_map();

int main(int argc, char** argv)
{
    Trick::MemoryManager memory;
    Trick::UdUnits units;
    if (units.read_default_xml() != 0)
    {
        return 1;
    }
    populate_sim_services_class_map();
    populate_sim_services_enum_map();
    Trick::IPPython input;
    if (argc > 1)
    {
        input.input_file = argv[1];
    }
    if (argc > 2)
    {
        // The scheduler ignores init's return value. Require termination via
        // ExecutiveException, not merely a nonzero return from init().
        try
        {
            input.init();
        }
        catch (const Trick::ExecutiveException& error)
        {
            const bool terminated
                = error.ret_code != 0 && error.message.find("Python startup failed") != std::string::npos;
            const bool skipped = input.parse("assert 'trick_startup_input_ran' not in globals()") == 0;
            input.shutdown();
            return terminated && skipped ? 0 : 4;
        }
        input.shutdown();
        std::fputs("Startup failure did not terminate the simulation\n", stderr);
        return 5;
    }
    if (input.init() != 0)
    {
        return 2;
    }
    if (argc > 1 && input.parse("assert trick_startup_input_ran is True") != 0)
    {
        input.shutdown();
        return 6;
    }
    const int result = input.parse(R"PY(
assert 'struct' in globals() and 'binascii' in globals()
import trick
import _sim_services, _swig_double, _swig_int, _swig_ref
clock = trick.GetTimeOfDayClock()
clock.rt_clock_ratio = 2.5
assert float(clock.rt_clock_ratio) == 2.5
generator = trick.RAND_GENERATOR()
values = generator.table
values[0] = 1.25
values[1] = 2.5
assert float(values[0]) == 1.25
assert float(values[1]) == 2.5
assert len(values) == 98
integrator = trick.getIntegrator(trick.Euler, 1, 0.25)
integrator.state[0] = 7.0
assert float(integrator.state[0]) == 7.0
)PY");
    input.shutdown();
    return result == 0 ? 0 : 3;
}
