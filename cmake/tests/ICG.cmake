cmake_minimum_required(VERSION 3.26)
file(REMOVE_RECURSE "${TEST_ROOT}")
file(MAKE_DIRECTORY "${TEST_ROOT}/input" "${TEST_ROOT}/output")
file(WRITE "${TEST_ROOT}/input/Smoke.hh" [=[
/** PURPOSE: (Native ICG CMake smoke fixture) */
#include <cstddef>
#include <cstdint>
#include <array>
struct Smoke {
    double position[3]; /**< (m) Position */
    std::uint32_t count; /**< (--) Count */
};
]=])
file(SHA256 "${TEST_ROOT}/input/Smoke.hh" original)
execute_process(COMMAND "${ICG}" ${FRONTEND_FLAGS} --version
    RESULT_VARIABLE result OUTPUT_VARIABLE output ERROR_VARIABLE error)
if(NOT result EQUAL 0 OR NOT output MATCHES "${TRICK_VERSION}")
    message(FATAL_ERROR "ICG version failed: ${output}\n${error}")
endif()
# Empty TRICK_CXX ensures the CMake path cannot rely on the legacy compiler hook.
execute_process(COMMAND "${CMAKE_COMMAND}" -E env --unset=TRICK_HOME TRICK_CXX=
    "${ICG}" ${FRONTEND_FLAGS} --icg-std=c++17 -o "${TEST_ROOT}/output" "${TEST_ROOT}/input/Smoke.hh"
    WORKING_DIRECTORY "${TEST_ROOT}" RESULT_VARIABLE result OUTPUT_VARIABLE output ERROR_VARIABLE error)
file(WRITE "${TEST_ROOT}/icg.log" "${output}\n${error}")
if(NOT result EQUAL 0 OR error MATCHES "Error initializing udunits")
    message(FATAL_ERROR "ICG header processing failed: ${output}\n${error}")
endif()
if(NOT EXISTS "${TEST_ROOT}/output/io_Smoke.cpp")
    message(FATAL_ERROR "ICG did not generate io_Smoke.cpp: ${output}\n${error}")
endif()
# This glob checks test outputs; it does not select build sources.
file(GLOB generated_files "${TEST_ROOT}/output/io_*.cpp")
list(LENGTH generated_files generated_count)
if(NOT generated_count EQUAL 1)
    message(FATAL_ERROR "ICG generated metadata for system headers: ${generated_files}")
endif()
file(READ "${TEST_ROOT}/output/io_Smoke.cpp" generated)
if(NOT generated MATCHES "Smoke" OR NOT generated MATCHES "position" OR NOT generated MATCHES "count")
    message(FATAL_ERROR "ICG output lacks expected class/field metadata")
endif()
file(SHA256 "${TEST_ROOT}/input/Smoke.hh" after)
if(NOT original STREQUAL after)
    message(FATAL_ERROR "ICG modified its input")
endif()

file(WRITE "${TEST_ROOT}/input/Invalid.hh" "struct Invalid { this is not valid C++; };\n")
execute_process(COMMAND "${CMAKE_COMMAND}" -E env --unset=TRICK_HOME TRICK_CXX=
    "${ICG}" ${FRONTEND_FLAGS} -o "${TEST_ROOT}/output" "${TEST_ROOT}/input/Invalid.hh"
    WORKING_DIRECTORY "${TEST_ROOT}" RESULT_VARIABLE result OUTPUT_VARIABLE output ERROR_VARIABLE error)
if(result EQUAL 0)
    message(FATAL_ERROR "ICG accepted an invalid header")
endif()
