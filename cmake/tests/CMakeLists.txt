set(TRICK_TEST_OLD_CMAKE "" CACHE FILEPATH "Optional CMake <3.26 for the minimum-version rejection test")

foreach(test_case IN ITEMS out-of-source in-source version invalid-version regeneration install)
    add_test(NAME "bootstrap.${test_case}"
        COMMAND "${CMAKE_COMMAND}"
            "-DCASE=${test_case}"
            "-DTRICK_SOURCE=${PROJECT_SOURCE_DIR}"
            "-DTEST_ROOT=${CMAKE_CURRENT_BINARY_DIR}/${test_case}"
            "-DGENERATOR=${CMAKE_GENERATOR}"
            "-DMAKE_PROGRAM=${CMAKE_MAKE_PROGRAM}"
            "-DC_COMPILER=${CMAKE_C_COMPILER}"
            "-DCXX_COMPILER=${CMAKE_CXX_COMPILER}"
            -P "${CMAKE_CURRENT_SOURCE_DIR}/Bootstrap.cmake")
    set_tests_properties("bootstrap.${test_case}" PROPERTIES LABELS bootstrap TIMEOUT 120)
endforeach()

if(TRICK_TEST_OLD_CMAKE)
    add_test(NAME bootstrap.minimum-version
        COMMAND "${CMAKE_COMMAND}"
            "-DCASE=minimum-version"
            "-DTRICK_SOURCE=${PROJECT_SOURCE_DIR}"
            "-DTEST_ROOT=${CMAKE_CURRENT_BINARY_DIR}/minimum-version"
            "-DOLD_CMAKE=${TRICK_TEST_OLD_CMAKE}"
            -P "${CMAKE_CURRENT_SOURCE_DIR}/Bootstrap.cmake")
    set_tests_properties(bootstrap.minimum-version PROPERTIES LABELS bootstrap TIMEOUT 30)
endif()
