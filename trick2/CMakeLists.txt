cmake_minimum_required(VERSION 4.1)
project(trick2 VERSION 0.1.0 LANGUAGES CXX)

include(CTest)
include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

option(TRICK2_BOOTSTRAP_ONLY "Build the runtime without the native C++26 reflection adapter" OFF)
option(TRICK2_BUILD_EXAMPLES "Build the runnable oscillator examples" ON)
option(TRICK2_WARNINGS_AS_ERRORS "Treat warnings in this project's targets as errors" OFF)

set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(TRICK2_BOOTSTRAP_ONLY)
    set(CMAKE_CXX_STANDARD 23)
    message(STATUS "Trick2 bootstrap: runtime and explicit descriptors only; reflection is NOT tested")
else()
    set(CMAKE_CXX_STANDARD 26)
    if(NOT "cxx_std_26" IN_LIST CMAKE_CXX_COMPILE_FEATURES)
        message(FATAL_ERROR
            "This compiler/CMake combination cannot select C++26. Use GCC 16, or\n"
            "explicitly set -DTRICK2_BOOTSTRAP_ONLY=ON for runtime development only.")
    endif()
    # GCC 16 requires this switch in addition to its C++26 language mode.
    # An alternate implementation can override the list, but must pass the probe.
    if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
        set(_reflection_defaults "-freflection")
    else()
        set(_reflection_defaults "")
    endif()
    set(TRICK2_REFLECTION_OPTIONS "${_reflection_defaults}" CACHE STRING
        "Semicolon-separated compiler options enabling standard C++26 reflection")
    try_compile(TRICK2_HAS_REFLECTION
        SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/cmake/check_reflection.cpp"
        CXX_STANDARD 26 CXX_STANDARD_REQUIRED ON CXX_EXTENSIONS OFF
        COMPILE_DEFINITIONS ${TRICK2_REFLECTION_OPTIONS}
        OUTPUT_VARIABLE _reflection_output)
    file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/reflection-probe.log" "${_reflection_output}")
    if(NOT TRICK2_HAS_REFLECTION)
        message(FATAL_ERROR
            "Native Trick2 needs C++26 reflection, annotations, and expansion statements.\n"
            "Use GCC 16 with -freflection, or another compiler that passes the probe.\n"
            "See ${CMAKE_CURRENT_BINARY_DIR}/reflection-probe.log.\n"
            "For runtime development only, explicitly set -DTRICK2_BOOTSTRAP_ONLY=ON.")
    endif()
endif()

function(trick2_project_warnings target)
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
        if(TRICK2_WARNINGS_AS_ERRORS)
            target_compile_options(${target} PRIVATE -Werror)
        endif()
    elseif(MSVC)
        target_compile_options(${target} PRIVATE /W4)
        if(TRICK2_WARNINGS_AS_ERRORS)
            target_compile_options(${target} PRIVATE /WX)
        endif()
    endif()
endfunction()

add_library(trick2_runtime STATIC src/registry.cpp src/simulation.cpp)
add_library(trick2::runtime ALIAS trick2_runtime)
set_target_properties(trick2_runtime PROPERTIES
    EXPORT_NAME runtime POSITION_INDEPENDENT_CODE ON)
target_include_directories(trick2_runtime PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)
# The runtime itself follows the selected build mode. Its public API needs C++20;
# a separately compiled legacy model need not include any Trick2 header at all.
target_compile_features(trick2_runtime PUBLIC cxx_std_20)
trick2_project_warnings(trick2_runtime)

set(_install_targets trick2_runtime)
if(NOT TRICK2_BOOTSTRAP_ONLY)
    add_library(trick2_reflection INTERFACE)
    add_library(trick2::reflection ALIAS trick2_reflection)
    set_target_properties(trick2_reflection PROPERTIES EXPORT_NAME reflection)
    target_link_libraries(trick2_reflection INTERFACE trick2::runtime)
    target_compile_features(trick2_reflection INTERFACE cxx_std_26)
    target_compile_options(trick2_reflection INTERFACE ${TRICK2_REFLECTION_OPTIONS})
    list(APPEND _install_targets trick2_reflection)
endif()

if(TRICK2_BUILD_EXAMPLES)
    # This target deliberately has no dependency on Trick2's headers or targets.
    add_library(trick2_legacy_model STATIC examples/mixed/model.cpp)
    set_target_properties(trick2_legacy_model PROPERTIES
        CXX_STANDARD 17 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO)
    target_include_directories(trick2_legacy_model PUBLIC examples/mixed)
    trick2_project_warnings(trick2_legacy_model)

    add_executable(trick2_mixed examples/mixed/main.cpp)
    target_link_libraries(trick2_mixed PRIVATE trick2::runtime trick2_legacy_model)
    trick2_project_warnings(trick2_mixed)

    if(NOT TRICK2_BOOTSTRAP_ONLY)
        add_executable(trick2_reflected
            examples/reflected/main.cpp examples/reflected/model.cpp
            examples/reflected/schema.cpp)
        target_link_libraries(trick2_reflected PRIVATE trick2::reflection)
        trick2_project_warnings(trick2_reflected)
    endif()
endif()

if(BUILD_TESTING)
    foreach(_test registry simulation rk4)
        add_executable(trick2_${_test}_test "tests/${_test}_test.cpp")
        target_link_libraries(trick2_${_test}_test PRIVATE trick2::runtime)
        trick2_project_warnings(trick2_${_test}_test)
        add_test(NAME ${_test} COMMAND trick2_${_test}_test)
    endforeach()

    if(TRICK2_BUILD_EXAMPLES)
        add_test(NAME example.mixed COMMAND trick2_mixed --verify)
        if(NOT TRICK2_BOOTSTRAP_ONLY)
            add_test(NAME example.reflected COMMAND trick2_reflected --verify)
        endif()
    endif()

    if(NOT TRICK2_BOOTSTRAP_ONLY)
        add_executable(trick2_reflection_test tests/reflection_test.cpp)
        target_link_libraries(trick2_reflection_test PRIVATE trick2::reflection)
        trick2_project_warnings(trick2_reflection_test)
        add_test(NAME reflection COMMAND trick2_reflection_test)

        function(trick2_reject_schema case diagnostic)
            add_test(NAME reflection.reject.${case}
                COMMAND ${CMAKE_COMMAND}
                    "-DCXX_COMPILER=${CMAKE_CXX_COMPILER}"
                    "-DCXX_COMPILER_ARG1=${CMAKE_CXX_COMPILER_ARG1}"
                    "-DCXX_FLAGS=${CMAKE_CXX_FLAGS}"
                    "-DREFLECTION_OPTIONS=${TRICK2_REFLECTION_OPTIONS}"
                    "-DSOURCE_DIR=${CMAKE_CURRENT_SOURCE_DIR}"
                    "-DBINARY_DIR=${CMAKE_CURRENT_BINARY_DIR}"
                    "-DCASE=${case}" "-DEXPECTED=${diagnostic}"
                    -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/ExpectCompileFailure.cmake")
        endfunction()
        trick2_reject_schema(zero_id "IDs must be nonzero")
        trick2_reject_schema(duplicate_ids "IDs must be unique")
        trick2_reject_schema(missing_annotation "requires exactly one trick2::Field annotation")
        trick2_reject_schema(duplicate_annotation "requires exactly one trick2::Field annotation")
        trick2_reject_schema(unsupported_type "must be double or const double")
        trick2_reject_schema(const_input "cannot have input access")
        trick2_reject_schema(base "base classes require an explicit adapter")
        trick2_reject_schema(private_state "non-public model fields require an explicit adapter")
        trick2_reject_schema(union "not a union")
    endif()
endif()

install(TARGETS ${_install_targets} EXPORT trick2Targets
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR})
install(DIRECTORY include/trick2 DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(EXPORT trick2Targets NAMESPACE trick2::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/trick2)
configure_package_config_file(cmake/trick2Config.cmake.in
    "${CMAKE_CURRENT_BINARY_DIR}/trick2Config.cmake"
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/trick2)
write_basic_package_version_file("${CMAKE_CURRENT_BINARY_DIR}/trick2ConfigVersion.cmake"
    VERSION ${PROJECT_VERSION} COMPATIBILITY ExactVersion)
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/trick2Config.cmake"
              "${CMAKE_CURRENT_BINARY_DIR}/trick2ConfigVersion.cmake"
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/trick2)
