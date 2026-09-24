#ifndef TRICK_PYTHON_MODULES_H
#define TRICK_PYTHON_MODULES_H

#ifdef __cplusplus
extern "C"
{
#endif

    /* Register the four core SWIG modules. Returns 0 on success, -1 on failure.
     * Python 3: call before Py_Initialize; an initialized interpreter is rejected.
     * Python 2: before Py_Initialize, append the modules to the built-in table;
     * after Py_Initialize, initialize them directly (IPPython's legacy hook),
     * preserving any Python error. The caller must hold the GIL in this case.
     * Call once per interpreter lifecycle: this function is not idempotent;
     * repeated Python 2 calls after initialization rerun the module initializers.
     * The executable owns interpreter initialization and finalization.
     * Simulation-generated modules remain the responsibility of the executable. */
    int trick_init_core_python_modules(void);

#ifdef __cplusplus
}
#endif

#endif
