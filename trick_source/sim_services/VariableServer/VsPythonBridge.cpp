// Adapter: the part of the Python bridge that needs Python.h (rewrite Phase 5).
//
// Lines that are not typed commands run through ip_parse() (VsServer.cpp), as
// every line did in the old server. While Python runs a line for a session,
// the var_* functions it calls reach that session through
// Server::current_session(), and stderr text from shortcuts.py's
// VarWriteStdio comes back as var_write_stdio, which the session also keeps
// for its error log.
//
// This file holds the one rule that needs the interpreter: a thread that
// holds the GIL must not wait for the memory lock with it. The main thread
// holds the memory lock for writing through a checkpoint load and calls
// IPPython::restart, which takes the GIL; a runner that waited for the
// memory lock while it held the GIL would deadlock with it.

#include <Python.h>

#include "trick/vs/adapter/Server.hh"

namespace Trick
{
    namespace vs
    {
        namespace adapter
        {

            std::shared_lock<std::shared_mutex> lock_shared_releasing_gil(std::shared_mutex& m)
            {
                std::shared_lock<std::shared_mutex> lock(m, std::try_to_lock);
                if (lock.owns_lock())
                    return lock;
                if (Py_IsInitialized() && PyGILState_Check())
                {
                    PyThreadState* state = PyEval_SaveThread();
                    lock.lock();
                    PyEval_RestoreThread(state);
                }
                else
                    lock.lock();
                return lock;
            }

            std::unique_lock<std::shared_mutex> lock_exclusive_releasing_gil(std::shared_mutex& m)
            {
                std::unique_lock<std::shared_mutex> lock(m, std::try_to_lock);
                if (lock.owns_lock())
                    return lock;
                if (Py_IsInitialized() && PyGILState_Check())
                {
                    PyThreadState* state = PyEval_SaveThread();
                    lock.lock();
                    PyEval_RestoreThread(state);
                }
                else
                    lock.lock();
                return lock;
            }

        } // namespace adapter
    } // namespace vs
} // namespace Trick
