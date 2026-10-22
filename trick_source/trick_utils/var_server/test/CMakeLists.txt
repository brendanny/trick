# Unit tests for libtrick_var_server. They link only that library and
# GoogleTest, never libtrick.
add_executable(trick_var_server_test
    Command_test.cpp
    Expected_test.cpp
    Fakes_test.cpp
    FieldDesc_test.cpp
    Schedule_test.cpp
    Snapshot_test.cpp
    WireTypes_test.cpp
)
target_link_libraries(trick_var_server_test PRIVATE trick_var_server GTest::gtest_main)
target_compile_features(trick_var_server_test PRIVATE cxx_std_17)

include(GoogleTest)
gtest_discover_tests(trick_var_server_test)
