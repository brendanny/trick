#include <Python.h>

#include "trick/IPPython.hh"
#include "trick/MemoryManager.hh"
#include "trick/UdUnits.hh"
#include "trick/python_modules.h"

#include <cstdlib>

extern "C" void init_swig_modules()
{
    if (trick_init_core_python_modules() != 0)
    {
        std::abort();
    }
}

void populate_sim_services_class_map();
void populate_sim_services_enum_map();

int main()
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
    if (input.init() != 0)
    {
        return 2;
    }
    const int result = input.parse(R"PY(
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
