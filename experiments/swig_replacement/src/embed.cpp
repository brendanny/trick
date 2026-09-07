#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <thread>
#include <cstdio>
// Import/run on a native worker thread to exercise PyGILState, then finalize.
// This is not yet a replacement IPPython.cpp or a subinterpreter test.
int main(int argc, char** argv) {
    if (argc != 4) { fprintf(stderr,"usage: poc_embed PYTHON SCRIPT BACKEND\n"); return 2; }
    PyConfig config; PyConfig_InitPythonConfig(&config);
    PyStatus status = PyConfig_SetBytesString(&config, &config.program_name, argv[1]);
    if (!PyStatus_Exception(status)) status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) { Py_ExitStatusException(status); }
    int result = 0; PyThreadState* state = PyEval_SaveThread();
    std::thread worker([&] {
        auto gil = PyGILState_Ensure();
        PyObject* args = Py_BuildValue("[ss]",argv[2],argv[3]);
        PySys_SetObject("argv",args); Py_DECREF(args);
        FILE* script = fopen(argv[2],"r");
        if (!script) result=2;
        else result = PyRun_SimpleFileEx(script,argv[2],1) ? 1 : 0;
        PyGILState_Release(gil);
    });
    worker.join(); PyEval_RestoreThread(state);
    if (Py_FinalizeEx() < 0) result=120;
    return result;
}
