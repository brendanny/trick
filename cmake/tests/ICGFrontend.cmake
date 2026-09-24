cmake_minimum_required(VERSION 3.26)
file(REMOVE_RECURSE "${TEST_ROOT}")
file(MAKE_DIRECTORY "${TEST_ROOT}/system" "${TEST_ROOT}/work")
# Both build systems expose the same explicit frontend controls.
foreach(version IN ITEMS 4.2.1 8.5.0)
    string(REPLACE "." ";" parts "${version}")
    list(GET parts 0 major)
    file(WRITE "${TEST_ROOT}/Input.hh" "#if __GNUC__ != ${major}\n#error wrong GNU dialect\n#endif\nstruct Frontend { int value; };\n")
    execute_process(COMMAND "${CMAKE_COMMAND}" -E env "TRICK_HOME=${TRICK_SOURCE}"
        "${ICG}" "--icg-gnu-version=${version}" --icg-strict-errors
        "--icg-system-dir=${TEST_ROOT}/system" --output-root "${TEST_ROOT}/output-${major}"
        "${TEST_ROOT}/Input.hh" WORKING_DIRECTORY "${TEST_ROOT}/work"
        RESULT_VARIABLE result OUTPUT_VARIABLE out ERROR_VARIABLE err)
    if(NOT result EQUAL 0)
        message(FATAL_ERROR "Runtime GNU policy failed: ${out}${err}")
    endif()
endforeach()
execute_process(COMMAND "${CMAKE_COMMAND}" -E env "TRICK_HOME=${TRICK_SOURCE}"
    "${ICG}" "--icg-system-dir=${TEST_ROOT}/missing" "${TEST_ROOT}/Input.hh"
    RESULT_VARIABLE result OUTPUT_VARIABLE out ERROR_VARIABLE err)
if(result EQUAL 0 OR NOT err MATCHES "compiler include directory is missing")
    message(FATAL_ERROR "Missing compiler include directory accepted: ${out}${err}")
endif()
# Strict mode must retain system-header notes as well as errors in legacy layout.
file(WRITE "${TEST_ROOT}/system/broken.hh" "struct Duplicate {};\nstruct Duplicate {};\n")
file(WRITE "${TEST_ROOT}/Input.hh" "#include <broken.hh>\nstruct Frontend {};\n")
file(MAKE_DIRECTORY "${TEST_ROOT}/legacy")
execute_process(COMMAND "${CMAKE_COMMAND}" -E env "TRICK_HOME=${TRICK_SOURCE}"
    "${ICG}" --icg-strict-errors "--icg-system-dir=${TEST_ROOT}/system"
    -o "${TEST_ROOT}/legacy" "${TEST_ROOT}/Input.hh"
    WORKING_DIRECTORY "${TEST_ROOT}/work" RESULT_VARIABLE result OUTPUT_VARIABLE out ERROR_VARIABLE err)
if(result EQUAL 0 OR NOT err MATCHES "previous definition")
    message(FATAL_ERROR "Strict system diagnostics lost note context: ${out}${err}")
endif()
