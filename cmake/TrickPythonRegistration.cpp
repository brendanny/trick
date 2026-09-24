#include <Python.h>

#include "trick/python_modules.h"

extern "C"
{
#if PY_MAJOR_VERSION >= 3
    PyObject* PyInit__sim_services();
    PyObject* PyInit__swig_double();
    PyObject* PyInit__swig_int();
    PyObject* PyInit__swig_ref();
#define TRICK_PY_INIT(module) PyInit_##module
#else
    void init_sim_services();
    void init_swig_double();
    void init_swig_int();
    void init_swig_ref();
#define TRICK_PY_INIT(module) init##module
#endif

    // Python 3 registers before initialization. IPPython's Python 2 hook runs
    // afterward, so initialize those modules directly in the existing runtime.
    int trick_init_core_python_modules()
    {
        if (Py_IsInitialized())
        {
#if PY_MAJOR_VERSION < 3
            init_sim_services();
            if (PyErr_Occurred())
            {
                return -1;
            }
            init_swig_double();
            if (PyErr_Occurred())
            {
                return -1;
            }
            init_swig_int();
            if (PyErr_Occurred())
            {
                return -1;
            }
            init_swig_ref();
            return PyErr_Occurred() ? -1 : 0;
#else
            return -1;
#endif
        }
        if (PyImport_AppendInittab("_sim_services", TRICK_PY_INIT(_sim_services)) != 0)
        {
            return -1;
        }
        if (PyImport_AppendInittab("_swig_double", TRICK_PY_INIT(_swig_double)) != 0)
        {
            return -1;
        }
        if (PyImport_AppendInittab("_swig_int", TRICK_PY_INIT(_swig_int)) != 0)
        {
            return -1;
        }
        return PyImport_AppendInittab("_swig_ref", TRICK_PY_INIT(_swig_ref));
    }
}
#undef TRICK_PY_INIT
