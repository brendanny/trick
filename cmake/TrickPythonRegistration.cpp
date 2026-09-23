#include <Python.h>

#include "trick/python_modules.h"

extern "C"
{
    PyObject* PyInit__sim_services();
    PyObject* PyInit__swig_double();
    PyObject* PyInit__swig_int();
    PyObject* PyInit__swig_ref();

    // Call before Py_Initialize. The executable decides when Python starts.
    int trick_init_core_python_modules()
    {
        if (Py_IsInitialized())
        {
            return -1;
        }
        if (PyImport_AppendInittab("_sim_services", PyInit__sim_services) != 0)
        {
            return -1;
        }
        if (PyImport_AppendInittab("_swig_double", PyInit__swig_double) != 0)
        {
            return -1;
        }
        if (PyImport_AppendInittab("_swig_int", PyInit__swig_int) != 0)
        {
            return -1;
        }
        return PyImport_AppendInittab("_swig_ref", PyInit__swig_ref);
    }
}
