find_package(GTest REQUIRED)

function(trick_utility_test name library)
    add_executable(${name} ${ARGN})
    # Includes and link dependencies must come from the library, not directory flags.
    target_link_libraries(${name} PRIVATE ${library} GTest::gtest_main)
    add_test(NAME utilities.${name} COMMAND ${name})
    set_tests_properties(utilities.${name} PROPERTIES LABELS utilities TIMEOUT 60)
endfunction()

trick_utility_test(math_test Trick::Math
    ../math/test/UnitTestEulerQuat.cpp
    ../math/test/UnitTestLDLtFactorization.cpp)
trick_utility_test(optimization_test Trick::Optimization ../optimization/test/UnitTestPDIPOptimization.cpp)
trick_utility_test(comm_test Trick::Comm ../comm/test/TCDevCopyTest.cpp)
trick_utility_test(connection_handlers_test Trick::ConnectionHandlers
    ../connection_handlers/test/TCPConnection_test.cpp
    ../connection_handlers/test/TCPClientListener_test.cpp
    ../connection_handlers/test/UDPConnection_test.cpp
    ../connection_handlers/test/MulticastGroup_test.cpp)
trick_utility_test(var_binary_parser_test Trick::VarBinaryParser
    ../var_binary_parser/test/TEST_var_binary_parser.cc)
trick_utility_test(units_test Trick::Units Units.cpp)

# An ordinary consumer must not inherit Trick's private -Wall/-Wextra options.
file(GENERATE OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/consumer-options-$<CONFIG>.txt"
    CONTENT "$<TARGET_PROPERTY:units_test,COMPILE_OPTIONS>\n")
add_test(NAME utilities.consumer-options
    COMMAND "${CMAKE_COMMAND}"
        "-DOPTIONS_FILE=${CMAKE_CURRENT_BINARY_DIR}/consumer-options-$<CONFIG>.txt"
        -P "${CMAKE_CURRENT_SOURCE_DIR}/ConsumerOptions.cmake")
set_tests_properties(utilities.consumer-options PROPERTIES LABELS utilities TIMEOUT 10)
