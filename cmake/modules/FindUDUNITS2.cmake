# CMake 3.26 has no built-in UDUNITS2 finder. Respect standard artifact overrides.
# A supplied root is authoritative: do not silently fall back to another prefix.
if(NOT DEFINED UDUNITS2_ROOT AND DEFINED ENV{UDUNITS2_ROOT})
    set(UDUNITS2_ROOT "$ENV{UDUNITS2_ROOT}")
endif()
if(UDUNITS2_ROOT)
    find_path(UDUNITS2_INCLUDE_DIR NAMES udunits2.h
        PATHS "${UDUNITS2_ROOT}/include" "${UDUNITS2_ROOT}/include/udunits2" NO_DEFAULT_PATH)
    find_library(UDUNITS2_LIBRARY NAMES udunits2
        PATHS "${UDUNITS2_ROOT}/lib/${CMAKE_LIBRARY_ARCHITECTURE}" "${UDUNITS2_ROOT}/lib" "${UDUNITS2_ROOT}/lib64" NO_DEFAULT_PATH)
else()
    find_path(UDUNITS2_INCLUDE_DIR NAMES udunits2.h PATH_SUFFIXES udunits2)
    find_library(UDUNITS2_LIBRARY NAMES udunits2)
endif()
include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(UDUNITS2 REQUIRED_VARS UDUNITS2_INCLUDE_DIR UDUNITS2_LIBRARY
    REASON_FAILURE_MESSAGE "Install UDUNITS-2 development files or set UDUNITS2_ROOT (or UDUNITS2_INCLUDE_DIR and UDUNITS2_LIBRARY).")
if(UDUNITS2_FOUND AND NOT TARGET UDUNITS2::UDUNITS2)
    add_library(UDUNITS2::UDUNITS2 UNKNOWN IMPORTED)
    set_target_properties(UDUNITS2::UDUNITS2 PROPERTIES
        IMPORTED_LOCATION "${UDUNITS2_LIBRARY}"
        INTERFACE_INCLUDE_DIRECTORIES "${UDUNITS2_INCLUDE_DIR}")
    include(CheckCSourceCompiles)
    include(CMakePushCheckState)
    cmake_push_check_state(RESET)
    set(CMAKE_REQUIRED_LIBRARIES UDUNITS2::UDUNITS2)
    unset(TRICK_UDUNITS2_LINKS CACHE)
    check_c_source_compiles("#include <udunits2.h>\nint main(void) { ut_system *s = ut_read_xml(0); ut_free_system(s); return 0; }" TRICK_UDUNITS2_LINKS)
    cmake_pop_check_state()
    if(NOT TRICK_UDUNITS2_LINKS)
        message(FATAL_ERROR "UDUNITS2 headers/library do not link. Select matching development files; static libraries may need their dependencies. See CMakeFiles/CMakeConfigureLog.yaml.")
    endif()
endif()
mark_as_advanced(UDUNITS2_INCLUDE_DIR UDUNITS2_LIBRARY)
