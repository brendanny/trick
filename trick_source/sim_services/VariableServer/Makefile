include $(dir $(lastword $(MAKEFILE_LIST)))../../../share/trick/makefiles/Makefile.common

# VsPythonBridge.cpp (rewrite Phase 5) uses the Python C API.
TRICK_CXXFLAGS += $(PYTHON_INCLUDES)

include ${TRICK_HOME}/share/trick/makefiles/Makefile.tricklib
