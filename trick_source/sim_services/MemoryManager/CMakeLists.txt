# The checkpoint agent and its parser belong with their MemoryManager owner;
# the separate CheckPointRestart scheduler is added to Core in B5.
trick_service(trick_mm MemoryManager)
target_sources(trick_mm PRIVATE
    ADefParseContext.cpp
    AttributesUtils.cpp
    MemoryManager.cpp
    MemoryManager_C_Intf.cpp
    MemoryManager_JSON_Intf.cpp
    MemoryManager_add_attr_info.cpp
    MemoryManager_add_checkpoint_alloc_dependency.cpp
    MemoryManager_add_shared_library_symbols.cpp
    MemoryManager_add_template_name_trans.cpp
    MemoryManager_add_var.cpp
    MemoryManager_alloc_depends.cpp
    MemoryManager_alloc_info_map.cpp
    MemoryManager_clear_memory.cpp
    MemoryManager_declare_var.cpp
    MemoryManager_delete_var.cpp
    MemoryManager_get_attributes_for_address.cpp
    MemoryManager_get_enumerated.cpp
    MemoryManager_get_size.cpp
    MemoryManager_get_stl_dependencies.cpp
    MemoryManager_get_type_attributes.cpp
    MemoryManager_io_src_intf.cpp
    MemoryManager_is_alloced.cpp
    MemoryManager_make_declaration.cpp
    MemoryManager_make_reference_attr.cpp
    MemoryManager_map_external_object.cpp
    MemoryManager_realloc.cpp
    MemoryManager_ref_allocate.cpp
    MemoryManager_ref_assignment.cpp
    MemoryManager_ref_attributes.cpp
    MemoryManager_ref_dim.cpp
    MemoryManager_ref_name.cpp
    MemoryManager_ref_name_from_address.cpp
    MemoryManager_ref_var.cpp
    MemoryManager_restore.cpp
    MemoryManager_restore_stls.cpp
    MemoryManager_set_checkpointagent.cpp
    MemoryManager_set_debug_level.cpp
    MemoryManager_strdup.cpp
    MemoryManager_write_checkpoint.cpp
    MemoryManager_write_var.cpp
    RefParseContext.cpp
    ReferenceUtils.cpp
    addr_bitfield.c
    extract_bitfield.c
    extract_unsigned_bitfield.c
    follow_address_path.c
    insert_bitfield.c
    ref_free.cpp
    ref_to_value.c
    trickTypeCharString.c
    vval.c
    wcs_ext.c
    ../CheckPointAgent/CheckPointAgent.cpp
    ../CheckPointAgent/ChkPtParseContext.cpp
    ../CheckPointAgent/ClassicCheckPointAgent.cpp
    ../CheckPointAgent/PythonPrint.cpp
)

file(MAKE_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/parsers")
foreach(parser IN ITEMS adef ref input)
    if(parser STREQUAL "input")
        set(parser_dir "${CMAKE_CURRENT_SOURCE_DIR}/../CheckPointAgent")
    else()
        set(parser_dir "${CMAKE_CURRENT_SOURCE_DIR}")
    endif()
    BISON_TARGET(${parser} "${parser_dir}/${parser}_parser.y"
        "${CMAKE_CURRENT_BINARY_DIR}/parsers/${parser}_parser.tab.cpp"
        DEFINES_FILE "${CMAKE_CURRENT_BINARY_DIR}/parsers/${parser}_parser.tab.hpp")
    FLEX_TARGET(${parser} "${parser_dir}/${parser}_parser.l"
        "${CMAKE_CURRENT_BINARY_DIR}/parsers/${parser}_parser.lex.cpp")
    ADD_FLEX_BISON_DEPENDENCY(${parser} ${parser})
    target_sources(trick_mm PRIVATE ${BISON_${parser}_OUTPUTS} ${FLEX_${parser}_OUTPUTS})
endforeach()
target_include_directories(trick_mm PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/parsers")
target_link_libraries(trick_mm PUBLIC Threads::Threads PRIVATE UDUNITS2::UDUNITS2 ${CMAKE_DL_LIBS})

# Small services required by the standalone memory manager, also reused by Core.
trick_service(trick_memory_support MemorySupport)
target_sources(trick_memory_support PRIVATE
    ../../sim_services/UdUnits/UdUnits.cpp
    ../../sim_services/UdUnits/map_trick_units_to_udunits.cpp
    ../../trick_utils/trick_adt/src/MapStrToPtr.c
    ../../trick_utils/trick_adt/src/bst.c
    ../../trick_utils/trick_adt/src/bubble_sort.c
    ../../trick_utils/trick_adt/src/dllist.c
    ../../trick_utils/trick_adt/src/lqueue.c
    ../../trick_utils/trick_adt/src/lstack.c
    ../../trick_utils/trick_adt/src/record_array.c
    ../../trick_utils/unicode/src/unicode_utils.c
    ../CheckPointRestart/next_attr_name.cpp
    ../CheckPointRestart/stl_type_name_convert.cpp
)
target_link_libraries(trick_memory_support PUBLIC UDUNITS2::UDUNITS2)
target_link_libraries(trick_mm PRIVATE Trick::MemorySupport)

if(BUILD_TESTING)
    add_executable(trick_mm_smoke "${PROJECT_SOURCE_DIR}/cmake/tests/MemoryManager.cpp"
        "${PROJECT_SOURCE_DIR}/cmake/tests/MessageSink.cpp")
    target_link_libraries(trick_mm_smoke PRIVATE Trick::MemoryManager Trick::MemorySupport)
    add_test(NAME runtime.memory_manager COMMAND trick_mm_smoke)
    set_tests_properties(runtime.memory_manager PROPERTIES LABELS "runtime;memory_manager")
endif()

option(TRICK_BUILD_RUNTIME_TESTS "Build existing GoogleTest runtime suites" OFF)
if(TRICK_BUILD_RUNTIME_TESTS)
    if(NOT BUILD_TESTING)
        message(FATAL_ERROR "TRICK_BUILD_RUNTIME_TESTS requires BUILD_TESTING")
    endif()
    find_package(GTest REQUIRED)
    foreach(suite IN ITEMS MM_creation_unittest Bitfield_tests MM_trick_type_char_string)
        add_executable(trick_${suite} "test/${suite}.cc" "${PROJECT_SOURCE_DIR}/cmake/tests/MessageSink.cpp")
        target_link_libraries(trick_${suite} PRIVATE Trick::MemoryManager GTest::gtest_main)
        add_test(NAME runtime.${suite} COMMAND trick_${suite})
        set_tests_properties(runtime.${suite} PROPERTIES LABELS "runtime;memory_manager")
    endforeach()
endif()
