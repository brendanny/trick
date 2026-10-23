# Unit tests for libtrick_var_server. They link only that library and
# GoogleTest, never libtrick.
add_executable(trick_var_server_test
    AddressFilter_test.cpp
    Buffers_test.cpp
    CommandParser_test.cpp
    Command_test.cpp
    Encoders_test.cpp
    Expected_test.cpp
    Fakes_test.cpp
    FieldDesc_test.cpp
    GoldenReplay_test.cpp
    ListenLoop_test.cpp
    Schedule_test.cpp
    Snapshot_test.cpp
    SocketFaults_test.cpp
    Sockets_test.cpp
    WireTypes_test.cpp
)
find_package(Threads REQUIRED)
target_link_libraries(trick_var_server_test PRIVATE trick_var_server GTest::gtest_main Threads::Threads)
target_compile_features(trick_var_server_test PRIVATE cxx_std_17)

# The golden replay test reads the captures of test/SIM_vs_conformance.
get_filename_component(_vs_conformance_dir "${CMAKE_CURRENT_SOURCE_DIR}/../../../../test/SIM_vs_conformance" ABSOLUTE)
target_compile_definitions(trick_var_server_test PRIVATE VS_CONFORMANCE_DIR="${_vs_conformance_dir}")

# With UDUNITS, the golden replay test also checks units conversions.
find_path(VS_UDUNITS_INCLUDE_DIR udunits2.h PATH_SUFFIXES udunits2)
find_library(VS_UDUNITS_LIBRARY udunits2)
if(VS_UDUNITS_INCLUDE_DIR AND VS_UDUNITS_LIBRARY)
    target_include_directories(trick_var_server_test PRIVATE ${VS_UDUNITS_INCLUDE_DIR})
    target_link_libraries(trick_var_server_test PRIVATE ${VS_UDUNITS_LIBRARY})
    target_compile_definitions(trick_var_server_test PRIVATE VS_HAVE_UDUNITS)
endif()

include(GoogleTest)
gtest_discover_tests(trick_var_server_test)
