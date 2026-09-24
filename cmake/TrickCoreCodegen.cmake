include("${CMAKE_CURRENT_LIST_DIR}/TrickCoreHeaders.cmake")
set(core_metadata_root "${CMAKE_CURRENT_BINARY_DIR}/metadata/$<CONFIG>")
set(core_inventory "")
set(core_generated)
foreach(header IN LISTS trick_core_headers)
    file(REAL_PATH "${PROJECT_SOURCE_DIR}/${header}" absolute_header)
    string(APPEND core_inventory "${absolute_header}\n")
    list(APPEND core_generated "${core_metadata_root}/io${absolute_header}.cpp")
endforeach()
file(CONFIGURE OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/core-headers.txt" CONTENT "${core_inventory}" @ONLY)
set(core_definitions "-DTRICK_VER=${PROJECT_VERSION_MAJOR}" "-DTRICK_MINOR=${PROJECT_VERSION_MINOR}")
if(TRICK_USE_ER7_UTILS)
    list(APPEND core_definitions -DUSE_ER7_UTILS_INTEGRATORS)
endif()
file(CONFIGURE OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/core-features.txt" CONTENT "${core_definitions}\n" @ONLY)
set(core_stamp "${core_metadata_root}/generation.stamp")
set(core_manifest "${core_metadata_root}/manifest.json")
set(core_maps "${core_metadata_root}/class_map.cpp" "${core_metadata_root}/extern_init_attr.h"
    "${core_metadata_root}/classes.resource")
add_custom_command(
    OUTPUT "${core_stamp}" "${core_manifest}" ${core_maps} ${core_generated}
    BYPRODUCTS "${core_metadata_root}/dependencies.d"
    COMMAND "${CMAKE_COMMAND}" -E make_directory "${core_metadata_root}"
    COMMAND "${CMAKE_COMMAND}" -E rm -f "${core_stamp}" "${core_manifest}"
    COMMAND Trick::ICG ${TRICK_ICG_FRONTEND_FLAGS} --output-root "${core_metadata_root}"
        --output-inventory "${CMAKE_CURRENT_BINARY_DIR}/core-headers.txt"
        -sim_services --icg-std=c++17 ${core_definitions}
        "-I${PROJECT_SOURCE_DIR}/include" "-I${PROJECT_SOURCE_DIR}/trick_source"
        "-I${PROJECT_SOURCE_DIR}/include/trick/compat" "-isystem${UDUNITS2_INCLUDE_DIR}"
        "${PROJECT_SOURCE_DIR}/include/trick/files_to_ICG.hh"
    DEPENDS Trick::ICG "${PROJECT_SOURCE_DIR}/include/trick/files_to_ICG.hh"
        "${CMAKE_CURRENT_BINARY_DIR}/core-headers.txt" "${CMAKE_CURRENT_BINARY_DIR}/core-features.txt"
    DEPFILE "${core_metadata_root}/dependencies.d"
    COMMENT "Generating core metadata and dependency manifest"
    VERBATIM
)
add_custom_target(trick_core_codegen DEPENDS "${core_stamp}" "${core_manifest}" ${core_maps} ${core_generated})
trick_service(trick_core_metadata CoreMetadata)
target_sources(trick_core_metadata PRIVATE ${core_generated} "${core_metadata_root}/class_map.cpp")
add_dependencies(trick_core_metadata trick_core_codegen)
target_link_libraries(trick_core_metadata PUBLIC Trick::Integrators PRIVATE Trick::MemorySupport)
target_compile_options(trick_core_metadata PRIVATE
    "$<$<CXX_COMPILER_ID:GNU,Clang,AppleClang>:-Wno-invalid-offsetof>")
if(BUILD_TESTING)
    add_test(NAME icg.core_manifest COMMAND "${CMAKE_COMMAND}"
        "-DMANIFEST=${core_manifest}" "-DINVENTORY=${CMAKE_CURRENT_BINARY_DIR}/core-headers.txt"
        "-DROOT=${core_metadata_root}" -P "${PROJECT_SOURCE_DIR}/cmake/tests/CoreManifest.cmake")
    set_tests_properties(icg.core_manifest PROPERTIES LABELS "icg;runtime")
    add_test(NAME icg.core_output_parity COMMAND "${CMAKE_COMMAND}"
        "-DICG=$<TARGET_FILE:trick-ICG>" "-DFRONTEND_FLAGS=${TRICK_ICG_FRONTEND_FLAGS}" "-DMANIFEST=${core_manifest}"
        "-DTRICK_SOURCE=${PROJECT_SOURCE_DIR}" "-DDEFINITIONS=${core_definitions}"
        "-DUDUNITS_INCLUDE=${UDUNITS2_INCLUDE_DIR}"
        "-DTEST_ROOT=${CMAKE_CURRENT_BINARY_DIR}/output-parity/$<CONFIG>"
        -P "${PROJECT_SOURCE_DIR}/cmake/tests/CoreOutputParity.cmake")
    set_tests_properties(icg.core_output_parity PROPERTIES LABELS "icg;runtime" TIMEOUT 120)
endif()
