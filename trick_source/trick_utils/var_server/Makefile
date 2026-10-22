TRICK_HOME := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))../../..)

# Build without ./configure: this library needs only a C++17 compiler.
CONFIG_MK = 1

include ${TRICK_HOME}/share/trick/makefiles/Makefile.common

# libtrick_var_server.a: the variable server core. It uses no other Trick
# library, so its unit tests link only this archive.
TRICK_LIB := $(TRICK_LIB_DIR)/libtrick_var_server.a
TRICK_CXXFLAGS += -std=c++17 -Wall -Wextra -Wpedantic

include ${TRICK_HOME}/share/trick/makefiles/Makefile.tricklib

trick: ${TRICK_LIB}
