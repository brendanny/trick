# libtrick_var_server: the variable server core (rewrite plan, Phase 1+).
#
# This directory builds two ways:
#   * as part of Trick (add_subdirectory from trick_source/trick_utils);
#   * on its own, with only a C++17 compiler and GoogleTest:
#       cmake -S trick_source/trick_utils/var_server -B build && cmake --build build && ctest --test-dir build
#     CI uses this to check the GCC 8.5 (RHEL 8) and macOS floors cheaply.
cmake_minimum_required(VERSION 3.20...4.4)

set(TRICK_VS_SOURCES
    Address.cpp
    AddressFilter.cpp
    AsciiEncoder.cpp
    Beacon.cpp
    BinaryEncoder.cpp
    CLocale.cpp
    Command.cpp
    CommandParser.cpp
    Connection.cpp
    Endpoint.cpp
    Fd.cpp
    FieldDesc.cpp
    FixedReply.cpp
    Interfaces.cpp
    LineReader.cpp
    ListenLoop.cpp
    Listener.cpp
    Packetizer.cpp
    Poller.cpp
    Schedule.cpp
    Snapshot.cpp
    SystemInterface.cpp
    Units.cpp
    WireTypes.cpp
    WriteQueue.cpp
)

if(COMMAND trick_add_library)
    trick_add_library(trick_var_server STATIC
        EXPORT_NAME var_server
        SOURCES ${TRICK_VS_SOURCES}
    )
    set(TRICK_VS_BUILD_TESTS ${TRICK_BUILD_TESTS})
else()
    project(TrickVariableServerCore LANGUAGES CXX)
    get_filename_component(_trick_root "${CMAKE_CURRENT_SOURCE_DIR}/../../.." ABSOLUTE)
    add_library(trick_var_server STATIC ${TRICK_VS_SOURCES})
    target_include_directories(trick_var_server PUBLIC "${_trick_root}/include")
    target_compile_features(trick_var_server PUBLIC cxx_std_17)
    set_target_properties(trick_var_server PROPERTIES CXX_EXTENSIONS OFF)
    option(BUILD_TESTING "Build the variable server core tests" ON)
    set(TRICK_VS_BUILD_TESTS ${BUILD_TESTING})
    if(TRICK_VS_BUILD_TESTS)
        enable_testing()
        find_package(GTest REQUIRED)
    endif()
endif()

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(trick_var_server PRIVATE -Wall -Wextra -Wpedantic)
endif()

if(TRICK_VS_BUILD_TESTS)
    add_subdirectory(test)
endif()

# libFuzzer targets (Clang only): cmake -DTRICK_VS_FUZZ=ON -DCMAKE_CXX_COMPILER=clang++
option(TRICK_VS_FUZZ "Build the variable server fuzz targets (Clang)" OFF)
if(TRICK_VS_FUZZ)
    add_subdirectory(fuzz)
endif()
