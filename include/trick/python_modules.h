#ifndef TRICK_PYTHON_MODULES_H
#define TRICK_PYTHON_MODULES_H

#ifdef __cplusplus
extern "C"
{
#endif

    /* Register the four core SWIG modules before Py_Initialize. Returns 0 on success.
     * Simulation-generated modules remain the responsibility of the executable. */
    int trick_init_core_python_modules(void);

#ifdef __cplusplus
}
#endif

#endif
