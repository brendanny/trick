include(GNUInstallDirs)
find_package(Perl 5.14 REQUIRED)
find_program(TRICK_SIMULATION_MAKE NAMES gmake make REQUIRED)
find_program(TRICK_SIMULATION_ZIP NAMES zip REQUIRED)
execute_process(COMMAND "${PERL_EXECUTABLE}" -MText::Balanced -MDigest::MD5 -e "exit 0"
    COMMAND_ERROR_IS_FATAL ANY)
set(TRICK_SDK_PYTHON_EXECUTABLE "${${python_package}_EXECUTABLE}")
set(SDK_ROOT "@SDK_ROOT@")
if(NOT CMAKE_SYSTEM_NAME MATCHES "^(Linux|Darwin)$" OR CMAKE_CROSSCOMPILING)
    message(FATAL_ERROR "The simulation SDK currently supports native Linux and macOS builds")
endif()
# Legacy simulation Makefiles use whitespace-separated lists. Reject paths they
# cannot represent instead of emitting a seemingly usable broken SDK.
foreach(path IN ITEMS "${PROJECT_SOURCE_DIR}" "${PROJECT_BINARY_DIR}" "${CMAKE_INSTALL_PREFIX}")
    if(path MATCHES "[ \t\n#$]")
        message(FATAL_ERROR "Legacy simulation tools require SDK/source/build paths without whitespace, # or $: ${path}")
    endif()
endforeach()
if(IS_ABSOLUTE "${CMAKE_INSTALL_LIBDIR}" OR CMAKE_INSTALL_LIBDIR MATCHES "(^|/)\\.\\.(/|$)")
    message(FATAL_ERROR "The relocatable SDK requires a relative CMAKE_INSTALL_LIBDIR")
endif()
set(TRICK_SDK_ROOT "${PROJECT_BINARY_DIR}/sdk/$<CONFIG>")
set(trick_sdk_archives trick_main trick_core trick_core_metadata trick_pyip trick_mm
    trick_memory_support trick_integrators trick_comm trick_connection_handlers
    trick_math trick_units trick_optimization trick_var_binary_parser)
if(TRICK_USE_ER7_UTILS)
    list(APPEND trick_sdk_archives er7_utils)
endif()
foreach(module IN ITEMS sim_services swig_double swig_int swig_ref)
    list(APPEND trick_sdk_archives trick_swig_${module})
endforeach()

set(sdk_stage_libraries "")
set(sdk_link_libraries "")
foreach(target IN LISTS trick_sdk_archives)
    string(APPEND sdk_stage_libraries
        "stage_link(\"$<TARGET_FILE:${target}>\" \"${CMAKE_INSTALL_LIBDIR}/$<TARGET_FILE_NAME:${target}>\")\n")
    if(APPLE)
        string(APPEND sdk_link_libraries " -Wl,-force_load,$(TRICK_LIB_DIR)/$<TARGET_FILE_NAME:${target}>")
    else()
        string(APPEND sdk_link_libraries " $(TRICK_LIB_DIR)/$<TARGET_FILE_NAME:${target}>")
    endif()
endforeach()
if(NOT APPLE)
    set(sdk_link_libraries "-Wl,--whole-archive ${sdk_link_libraries} -Wl,--no-whole-archive")
endif()
# Like CMake's own target include handling, do not move a compiler's
# implicit system directory ahead of its C++ wrappers (include_next).
set(sdk_udunits_includes "-isystem${UDUNITS2_INCLUDE_DIR}")
file(REAL_PATH "${UDUNITS2_INCLUDE_DIR}" sdk_udunits_include_real)
foreach(path IN LISTS CMAKE_CXX_IMPLICIT_INCLUDE_DIRECTORIES)
    file(REAL_PATH "${path}" sdk_implicit_include_real)
    if(sdk_udunits_include_real STREQUAL sdk_implicit_include_real)
        set(sdk_udunits_includes "")
    endif()
endforeach()
set(sdk_python_includes "")
foreach(path IN LISTS ${python_package}_INCLUDE_DIRS)
    string(APPEND sdk_python_includes " -I${path}")
endforeach()
get_filename_component(sdk_udunits_libdir "${UDUNITS2_LIBRARY}" DIRECTORY)
set(sdk_external_libraries "$<TARGET_FILE:Trick::Python> ${UDUNITS2_LIBRARY} -pthread")
foreach(lib IN LISTS CMAKE_DL_LIBS)
    string(APPEND sdk_external_libraries " -l${lib}")
endforeach()
set(sdk_platform_flags)
if(APPLE)
    if(CMAKE_OSX_SYSROOT)
        list(APPEND sdk_platform_flags "-isysroot${CMAKE_OSX_SYSROOT}")
    endif()
    if(CMAKE_OSX_DEPLOYMENT_TARGET)
        list(APPEND sdk_platform_flags "-mmacosx-version-min=${CMAKE_OSX_DEPLOYMENT_TARGET}")
    endif()
    list(LENGTH CMAKE_OSX_ARCHITECTURES sdk_arch_count)
    if(sdk_arch_count GREATER 1)
        message(FATAL_ERROR "The simulation SDK requires a single native architecture; universal builds need a separate toolchain contract")
    endif()
    foreach(arch IN LISTS CMAKE_OSX_ARCHITECTURES)
        if(NOT arch STREQUAL CMAKE_HOST_SYSTEM_PROCESSOR)
            message(FATAL_ERROR "The simulation SDK currently requires the native macOS architecture ${CMAKE_HOST_SYSTEM_PROCESSOR}")
        endif()
    endforeach()
elseif(CMAKE_SYSROOT)
    list(APPEND sdk_platform_flags "--sysroot=${CMAKE_SYSROOT}")
endif()
string(JOIN " " sdk_platform_make_flags ${sdk_platform_flags})
set(sdk_link_options "${sdk_platform_make_flags} ${CMAKE_EXE_LINKER_FLAGS} -Wl,-rpath,${sdk_udunits_libdir} -Wl,-rpath,$<TARGET_FILE_DIR:Trick::Python>")
if(NOT APPLE)
    string(APPEND sdk_external_libraries " -lm -lrt")
    string(APPEND sdk_link_options " -Wl,--export-dynamic")
endif()
separate_arguments(sdk_compiler_flags NATIVE_COMMAND "${CMAKE_CXX_FLAGS}")
execute_process(COMMAND "${CMAKE_CXX_COMPILER}" ${sdk_compiler_flags} ${sdk_platform_flags} -std=c++17 -dM -E -x c++ /dev/null
    OUTPUT_VARIABLE sdk_predefines COMMAND_ERROR_IS_FATAL ANY)
# Builtin operators do not necessarily appear in -dM (notably in Clang).
set(sdk_feature_probe "")
foreach(operator IN ITEMS __has_include __has_include_next __has_cpp_attribute __has_builtin __has_attribute __has_feature)
    string(APPEND sdk_feature_probe "#if defined(${operator})\nTRICK_FEATURE \"${operator}\" 1\n#else\nTRICK_FEATURE \"${operator}\" 0\n#endif\n")
endforeach()
file(WRITE "${PROJECT_BINARY_DIR}/sdk-feature-probe.cpp" "${sdk_feature_probe}")
execute_process(COMMAND "${CMAKE_CXX_COMPILER}" ${sdk_compiler_flags} ${sdk_platform_flags} -std=c++17 -E -P -x c++
    "${PROJECT_BINARY_DIR}/sdk-feature-probe.cpp"
    OUTPUT_VARIABLE sdk_feature_presence COMMAND_ERROR_IS_FATAL ANY)
string(REPLACE "\"" "" sdk_feature_presence "${sdk_feature_presence}")
string(REPLACE "TRICK_FEATURE" "#trick_feature" sdk_feature_presence "${sdk_feature_presence}")
string(APPEND sdk_predefines "${sdk_feature_presence}")
file(WRITE "${PROJECT_BINARY_DIR}/sdk-model-predefines.txt" "${sdk_predefines}")
configure_file("${CMAKE_CURRENT_LIST_DIR}/sdk/sdk.env.in" "sdk-env.in" @ONLY)
file(GENERATE OUTPUT "${PROJECT_BINARY_DIR}/sdk-config/$<CONFIG>/sdk.env" INPUT "${PROJECT_BINARY_DIR}/sdk-env.in")
configure_file("${CMAKE_CURRENT_LIST_DIR}/sdk/config_user.mk.in" "sdk-config-user.in" @ONLY)
configure_file("${CMAKE_CURRENT_LIST_DIR}/sdk/cmake-sdk.mk.in" "sdk-config.in" @ONLY)
configure_file("${CMAKE_CURRENT_LIST_DIR}/sdk/StageSDK.cmake.in" "sdk-stage.in" @ONLY)
file(GENERATE OUTPUT "${PROJECT_BINARY_DIR}/sdk-config/$<CONFIG>/config_user.mk"
    INPUT "${PROJECT_BINARY_DIR}/sdk-config-user.in")
file(GENERATE OUTPUT "${PROJECT_BINARY_DIR}/sdk-config/$<CONFIG>/cmake-sdk.mk"
    INPUT "${PROJECT_BINARY_DIR}/sdk-config.in")
file(GENERATE OUTPUT "${PROJECT_BINARY_DIR}/sdk-config/$<CONFIG>/stage.cmake"
    INPUT "${PROJECT_BINARY_DIR}/sdk-stage.in")
add_custom_target(trick_sdk ALL
    COMMAND "${CMAKE_COMMAND}" -P "${PROJECT_BINARY_DIR}/sdk-config/$<CONFIG>/stage.cmake"
    DEPENDS ${trick_sdk_archives} trick-ICG
        trick_sim_services_proxy trick_swig_double_proxy trick_swig_int_proxy trick_swig_ref_proxy
    COMMENT "Staging the build-tree Trick simulation SDK" VERBATIM)
message(STATUS "Trick build-tree SDK: ${PROJECT_BINARY_DIR}/sdk/<configuration>")
if(BUILD_TESTING)
    add_test(NAME sdk.simulation COMMAND "${CMAKE_COMMAND}"
        "-DSDK=${TRICK_SDK_ROOT}" "-DFIXTURE=${PROJECT_SOURCE_DIR}/cmake/examples/SIM_sdk"
        "-DTEST_ROOT=${PROJECT_BINARY_DIR}/sdk-tests/$<CONFIG>/simulation"
        -P "${PROJECT_SOURCE_DIR}/cmake/tests/SDK.cmake")
    set_tests_properties(sdk.simulation PROPERTIES LABELS sdk TIMEOUT 240)

    add_test(NAME sdk.compiler_guard COMMAND "${CMAKE_COMMAND}"
        "-DICG=$<TARGET_FILE:trick-ICG>" "-DPROFILE=${PROJECT_BINARY_DIR}/sdk-model-predefines.txt"
        "-DTEST_ROOT=${PROJECT_BINARY_DIR}/sdk-tests/$<CONFIG>/compiler-guard"
        -P "${PROJECT_SOURCE_DIR}/cmake/tests/ModelCompilerGuard.cmake")
    set_tests_properties(sdk.compiler_guard PROPERTIES LABELS sdk TIMEOUT 120)
endif()
