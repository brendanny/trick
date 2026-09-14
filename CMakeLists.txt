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

configure_file(cmake/TrickVersionInfo.cmake.in TrickVersionInfo.cmake @ONLY)

include(CTest)
if(BUILD_TESTING)
    add_subdirectory(cmake/tests)
endif()

message(STATUS "Trick ${TRICK_VERSION}: CMake developer preview (A2)")
message(WARNING
    "This configuration-only preview does not build or install Trick yet. "
    "Use the documented Autoconf/Make route for a usable installation. "
    "See docs/development/build-system/bootstrap.md.")

# Avoid a successful empty installation that looks like a usable Trick SDK.
install(CODE [[
    message(FATAL_ERROR "Trick's CMake preview cannot install an SDK yet.")
]])
