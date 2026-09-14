include_guard(GLOBAL)

# Preflight selections, not promises that later runtime/ICG targets exist yet.
set(TRICK_DEPENDENCY_PROFILE "UTILITIES" CACHE STRING "Dependency preflight: UTILITIES, RUNTIME, ICG, ALL")
set_property(CACHE TRICK_DEPENDENCY_PROFILE PROPERTY STRINGS UTILITIES RUNTIME ICG ALL)
if(NOT TRICK_DEPENDENCY_PROFILE MATCHES "^(UTILITIES|RUNTIME|ICG|ALL)$")
    message(FATAL_ERROR "Invalid TRICK_DEPENDENCY_PROFILE='${TRICK_DEPENDENCY_PROFILE}'; choose UTILITIES, RUNTIME, ICG or ALL.")
endif()

if(NOT TRICK_DEPENDENCY_PROFILE STREQUAL "UTILITIES" AND CMAKE_CROSSCOMPILING)
    message(FATAL_ERROR "Dependency preflight currently requires a native build. Host/target separation for cross builds is introduced in E3.")
endif()

if(TRICK_DEPENDENCY_PROFILE MATCHES "^(RUNTIME|ALL)$")
    include("${CMAKE_CURRENT_LIST_DIR}/TrickRuntimeDependencies.cmake")
endif()
if(TRICK_DEPENDENCY_PROFILE MATCHES "^(ICG|ALL)$")
    include("${CMAKE_CURRENT_LIST_DIR}/TrickLLVM.cmake")
endif()

# Plain-text report avoids serializing arbitrary paths into executable CMake code.
set(report "Trick dependency preflight: ${TRICK_DEPENDENCY_PROFILE}\nCMake: ${CMAKE_VERSION}\nSystem: ${CMAKE_SYSTEM_NAME} ${CMAKE_SYSTEM_VERSION} ${CMAKE_SYSTEM_PROCESSOR}\nGenerator: ${CMAKE_GENERATOR}\nC: ${CMAKE_C_COMPILER} (${CMAKE_C_COMPILER_ID} ${CMAKE_C_COMPILER_VERSION})\nCXX: ${CMAKE_CXX_COMPILER} (${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION})\n")
set(report_variables)
if(TRICK_DEPENDENCY_PROFILE MATCHES "^(RUNTIME|ALL)$")
    list(APPEND report_variables BISON_EXECUTABLE BISON_VERSION FLEX_EXECUTABLE FLEX_VERSION SWIG_EXECUTABLE SWIG_VERSION PERL_EXECUTABLE PERL_VERSION_STRING TRICK_PYTHON_MAJOR
        ${python_package}_EXECUTABLE ${python_package}_VERSION ${python_package}_INCLUDE_DIRS ${python_package}_LIBRARIES UDUNITS2_INCLUDE_DIR UDUNITS2_LIBRARY)
endif()
if(TRICK_DEPENDENCY_PROFILE MATCHES "^(ICG|ALL)$")
    list(APPEND report_variables LLVM_DIR LLVM_PACKAGE_VERSION Clang_DIR)
endif()
foreach(variable IN LISTS report_variables)
    if(DEFINED ${variable})
        string(APPEND report "${variable}: ${${variable}}\n")
    endif()
endforeach()
file(WRITE "${PROJECT_BINARY_DIR}/TrickDependencies.txt" "${report}")
message(STATUS "Trick dependency profile: ${TRICK_DEPENDENCY_PROFILE}; details: ${PROJECT_BINARY_DIR}/TrickDependencies.txt")
