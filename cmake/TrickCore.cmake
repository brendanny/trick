trick_service(trick_core Core)
set_target_properties(trick_core PROPERTIES OUTPUT_NAME trick)
include("${CMAKE_CURRENT_LIST_DIR}/TrickCoreSources.cmake")
target_link_libraries(trick_core PUBLIC Trick::Integrators Trick::MemoryManager
    Trick::Comm Trick::ConnectionHandlers Trick::Math Trick::Units
    PRIVATE Trick::MemorySupport Trick::VarBinaryParser ${CMAKE_DL_LIBS})
# Core and MM contain references to each other (messages and allocation).
# Declare the real static cycle: CMake repeats the connected component as needed.
target_link_libraries(trick_mm PRIVATE Trick::Core)

# The simulation-generated memory_init entry point remains an external contract.
trick_service(trick_main Main)
target_sources(trick_main PRIVATE mains/master.cpp)
target_link_libraries(trick_main PUBLIC Trick::Core)

# A narrow retention hook for closed-subsystem consumers. Full runtime metadata
# retention is provided with the Python runtime in B6.
function(trick_retain_metadata target)
    target_link_libraries(${target} PRIVATE Trick::CoreMetadata Trick::Core)
    set_target_properties(${target} PROPERTIES ENABLE_EXPORTS ON)
    foreach(type IN LISTS ARGN)
        if(APPLE)
            set(prefix "_")
        else()
            set(prefix "")
        endif()
        target_link_options(${target} PRIVATE "LINKER:-u,${prefix}init_attr${type}_c_intf")
    endforeach()
endfunction()

if(BUILD_TESTING)
    add_executable(trick_core_smoke "${PROJECT_SOURCE_DIR}/cmake/tests/Core.cpp"
        "${PROJECT_SOURCE_DIR}/cmake/tests/MessageSink.cpp")
    trick_retain_metadata(trick_core_smoke Trick__Environment)
    add_test(NAME runtime.core COMMAND trick_core_smoke)
    set_tests_properties(runtime.core PROPERTIES LABELS runtime)
    if(TRICK_BUILD_RUNTIME_TESTS)
        find_package(GTest CONFIG REQUIRED)
        add_executable(trick_scheduled_queue_test ScheduledJobQueue/test/ScheduledJobQueue_test.cpp
            "${PROJECT_SOURCE_DIR}/cmake/tests/MessageSink.cpp")
        trick_retain_metadata(trick_scheduled_queue_test Trick__JobData Trick__SimObject)
        target_link_libraries(trick_scheduled_queue_test PRIVATE GTest::gtest_main)
        add_test(NAME runtime.scheduled_queue COMMAND trick_scheduled_queue_test)
        set_tests_properties(runtime.scheduled_queue PROPERTIES LABELS runtime)
    endif()
endif()
