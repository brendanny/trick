#include <Python.h>

#include "trick/Euler_Integrator.hh"
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
    // Exercise retained metadata through the runtime allocator as well as SWIG.
    if (!memory.declare_var("Trick::Environment consumer_environment"))
    {
        return 2;
    }
    init_swig_modules();
    Py_Initialize();
    const int status = PyRun_SimpleString("import trick\n"
                                          "clock = trick.GetTimeOfDayClock()\n"
                                          "clock.rt_clock_ratio = 2.5\n"
                                          "assert float(clock.rt_clock_ratio) == 2.5\n");
    if (status != 0)
    {
        PyErr_Print();
    }
    Py_Finalize();
    return status == 0 ? 0 : 3;
}
