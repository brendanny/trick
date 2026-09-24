# Modern default; legacy major requires explicit selection.
set(TRICK_PYTHON_MAJOR "3" CACHE STRING "Embedded Python major (2 or 3)")
set_property(CACHE TRICK_PYTHON_MAJOR PROPERTY STRINGS 2 3)
if(NOT TRICK_PYTHON_MAJOR MATCHES "^[23]$")
    message(FATAL_ERROR "TRICK_PYTHON_MAJOR must be 2 or 3")
endif()
set(python_package "Python${TRICK_PYTHON_MAJOR}")
# Request both in one call: never pair a python-config from a different install.
find_package(${python_package} REQUIRED COMPONENTS Interpreter Development.Embed)
if(TRICK_PYTHON_MAJOR STREQUAL "2")
    message(WARNING "DEPRECATED: Python ${Python2_VERSION} (${Python2_EXECUTABLE}) is enabled for compatibility only. Upgrade to Python 3 and configure with -DTRICK_PYTHON_MAJOR=3. Python 2 support will be removed in Trick 27.")
endif()
add_library(Trick::Python ALIAS ${python_package}::Python)

include(CheckCXXSourceRuns)
include(CMakePushCheckState)
cmake_push_check_state(RESET)
set(CMAKE_REQUIRED_LIBRARIES ${python_package}::Python)
# Recheck when the user changes artifact hints in an existing cache.
unset(TRICK_PYTHON_EMBED_MATCH CACHE)
check_cxx_source_runs("
#include <Python.h>
#include <cstdio>
#if PY_MAJOR_VERSION != ${${python_package}_VERSION_MAJOR} || PY_MINOR_VERSION != ${${python_package}_VERSION_MINOR}
#error Interpreter and headers disagree
#endif
int main() {
    int major = 0, minor = 0;
    if (std::sscanf(Py_GetVersion(), \"%d.%d\", &major, &minor) != 2) return 1;
    if (major != PY_MAJOR_VERSION || minor != PY_MINOR_VERSION) return 2;
    Py_Initialize();
    if (!Py_IsInitialized()) return 3;
    Py_Finalize();
    return 0;
}" TRICK_PYTHON_EMBED_MATCH)
cmake_pop_check_state()
if(NOT TRICK_PYTHON_EMBED_MATCH)
    message(FATAL_ERROR "Selected Python interpreter, headers and embed library do not compile/link/run consistently. Use ${python_package}_EXECUTABLE, ${python_package}_INCLUDE_DIR and ${python_package}_LIBRARY from one installation. See CMakeFiles/CMakeConfigureLog.yaml.")
endif()
