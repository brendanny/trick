cmake_minimum_required(VERSION 3.20)
project(icg_legacy_baseline LANGUAGES C CXX)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Evidence-only build of the existing sources. Never installs over bin/trick-ICG
# and deliberately does not include or alter the production build configuration.
find_package(LLVM 17 REQUIRED CONFIG)
if(NOT LLVM_VERSION_MAJOR EQUAL 17)
    message(FATAL_ERROR "The legacy evidence lane requires LLVM 17")
endif()
find_package(Clang REQUIRED CONFIG HINTS "${LLVM_DIR}/../clang" NO_DEFAULT_PATH)
find_path(UDUNITS_INCLUDE_DIR udunits2.h REQUIRED)
find_library(UDUNITS_LIBRARY NAMES udunits2 REQUIRED)
get_filename_component(TRICK_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../.." ABSOLUTE)
set(LEGACY_SOURCE "${TRICK_ROOT}/trick_source/codegen/Interface_Code_Gen")
file(GLOB legacy_sources CONFIGURE_DEPENDS "${LEGACY_SOURCE}/*.cpp")
add_executable(trick-ICG-baseline ${legacy_sources}
    "${TRICK_ROOT}/trick_source/sim_services/UdUnits/map_trick_units_to_udunits.cpp")
set_target_properties(trick-ICG-baseline PROPERTIES
    CXX_STANDARD 17 CXX_STANDARD_REQUIRED YES)
target_include_directories(trick-ICG-baseline SYSTEM PRIVATE
    ${LLVM_INCLUDE_DIRS} ${CLANG_INCLUDE_DIRS} ${UDUNITS_INCLUDE_DIR})
target_include_directories(trick-ICG-baseline PRIVATE "${TRICK_ROOT}/include")
target_compile_definitions(trick-ICG-baseline PRIVATE
    __STDC_CONSTANT_MACROS __STDC_FORMAT_MACROS __STDC_LIMIT_MACROS
    LIBCLANG_MAJOR=${LLVM_VERSION_MAJOR} LIBCLANG_MINOR=${LLVM_VERSION_MINOR}
    LIBCLANG_PATCHLEVEL=${LLVM_VERSION_PATCH}
    LLVM_HOME="${LLVM_TOOLS_BINARY_DIR}/.." TRICK_VERSION="legacy-baseline")
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    target_compile_definitions(trick-ICG-baseline PRIVATE
        TRICK_GCC_VERSION="${CMAKE_CXX_COMPILER_VERSION}")
endif()
if(NOT LLVM_ENABLE_RTTI)
    target_compile_options(trick-ICG-baseline PRIVATE -fno-rtti)
endif()
if(TARGET clang-cpp)
    target_link_libraries(trick-ICG-baseline PRIVATE clang-cpp LLVM ${UDUNITS_LIBRARY})
else()
    target_link_libraries(trick-ICG-baseline PRIVATE clangFrontend ${UDUNITS_LIBRARY})
endif()
configure_file(build-info.txt.in build-info.txt @ONLY)
