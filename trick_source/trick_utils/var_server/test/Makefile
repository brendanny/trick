TRICK_HOME := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))../../../..)

CONFIG_MK = 1

include ${TRICK_HOME}/share/trick/makefiles/Makefile.common

# These tests link only libtrick_var_server.a and GoogleTest, never libtrick.
GTEST_HOME ?= /usr
VS_LIB := $(TRICK_LIB_DIR)/libtrick_var_server.a
TEST_SRCS := $(wildcard *_test.cpp)
TEST_EXE := var_server_core_test

CXXFLAGS_TEST := -std=c++17 -Wall -Wextra -g -I$(TRICK_HOME)/include -I$(GTEST_HOME)/include $(TRICK_CXXFLAGS)
LIBS_TEST := $(VS_LIB) -L$(GTEST_HOME)/lib64 -L$(GTEST_HOME)/lib -lgtest_main -lgtest -lpthread

.PHONY: all test clean FORCE

all: $(TEST_EXE)

test: $(TEST_EXE)
	./$(TEST_EXE) --gtest_output=xml:$(TRICK_HOME)/trick_test/VariableServerCore.xml

# Rebuild the library first, so the test never links a stale archive.
$(VS_LIB): FORCE
	@ $(MAKE) -C .. trick

$(TEST_EXE): $(TEST_SRCS) $(VS_LIB) $(wildcard $(TRICK_HOME)/include/trick/vs/*.hh $(TRICK_HOME)/include/trick/vs/*/*.hh)
	$(TRICK_CXX) $(CXXFLAGS_TEST) $(TEST_SRCS) $(LIBS_TEST) $(TRICK_LDFLAGS) -o $@

clean:
	$(RM) $(TEST_EXE)
