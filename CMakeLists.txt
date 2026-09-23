cmake_minimum_required(VERSION 3.26)

# Resolve aliases too: an in-source configure can overwrite the legacy Makefile.
file(REAL_PATH "${CMAKE_CURRENT_SOURCE_DIR}" trick_source_dir)
file(REAL_PATH "${CMAKE_CURRENT_BINARY_DIR}" trick_binary_dir)
if(trick_source_dir STREQUAL trick_binary_dir)
    message(FATAL_ERROR
        "Trick requires an out-of-source build. Use cmake -S <source> -B <build>. "
        "Remove only CMakeCache.txt and CMakeFiles created by this failed attempt; "
        "do not remove Trick's checked-in Makefile.")
endif()

include(cmake/TrickVersion.cmake)
trick_read_version("${CMAKE_CURRENT_SOURCE_DIR}/share/trick/trick_ver.txt")
project(Trick VERSION "${TRICK_VERSION_NUMBER}" LANGUAGES C CXX)

option(TRICK_BUILD_ICG "Build the existing native interface code generator" OFF)

option(TRICK_BUILD_MEMORY_MANAGER "Build the native memory manager and parsers" OFF)

include(cmake/TrickCompilers.cmake)
include(cmake/TrickDependencies.cmake)

configure_file(cmake/TrickVersionInfo.cmake.in TrickVersionInfo.cmake @ONLY)

include(CTest)
option(TRICK_BUILD_UTILITIES "Build the native utility archives" ON)
option(TRICK_BUILD_UTILITY_TESTS "Build focused utility tests (requires GoogleTest)" OFF)
if(TRICK_BUILD_UTILITY_TESTS AND (NOT BUILD_TESTING OR NOT TRICK_BUILD_UTILITIES))
    message(FATAL_ERROR "Utility tests require BUILD_TESTING and TRICK_BUILD_UTILITIES")
endif()
if(TRICK_BUILD_UTILITIES)
    add_subdirectory(trick_source/trick_utils)
endif()
if(TRICK_BUILD_ICG)
    add_subdirectory(trick_source/codegen/Interface_Code_Gen)
endif()
if(TRICK_BUILD_MEMORY_MANAGER)
    add_subdirectory(trick_source/sim_services)
endif()
if(BUILD_TESTING)
    add_subdirectory(cmake/tests)
endif()

message(STATUS "Trick ${TRICK_VERSION}: CMake developer preview (A5)")
message(WARNING
    "This preview builds selected utilities and ICG, not a complete Trick SDK. "
    "Use the documented Autoconf/Make route for a usable installation. "
    "See docs/development/build-system/icg.md.")

# Avoid a successful empty installation that looks like a usable Trick SDK.
install(CODE [[
    message(FATAL_ERROR "Trick's CMake preview cannot install an SDK yet.")
]])
