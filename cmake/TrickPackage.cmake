include(CMakePackageConfigHelpers)
set(trick_package_dir "${CMAKE_INSTALL_LIBDIR}/cmake/Trick")
set_target_properties(trick-ICG PROPERTIES EXPORT_NAME ICG)
set_target_properties(trick_runtime PROPERTIES EXPORT_NAME Runtime)
set_target_properties(trick_python_registration PROPERTIES EXPORT_NAME PythonRegistration)
foreach(module IN ITEMS sim_services swig_double swig_int swig_ref)
    set_target_properties(trick_swig_${module} PROPERTIES EXPORT_NAME "SWIG_${module}")
endforeach()
install(TARGETS trick_python_registration trick_runtime EXPORT TrickTargets
    ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}")
install(EXPORT TrickTargets NAMESPACE Trick:: DESTINATION "${trick_package_dir}")
export(EXPORT TrickTargets NAMESPACE Trick:: FILE "${PROJECT_BINARY_DIR}/package/TrickTargets.cmake")
set(Trick_PYTHON_VERSION "${${python_package}_VERSION_MAJOR}.${${python_package}_VERSION_MINOR}")
set(trick_package_python_dir "share/trick/swig")
configure_package_config_file("${CMAKE_CURRENT_LIST_DIR}/TrickConfig.cmake.in"
    "${PROJECT_BINARY_DIR}/install-package/TrickConfig.cmake"
    INSTALL_DESTINATION "${trick_package_dir}"
    PATH_VARS trick_package_python_dir)
set(trick_package_python_dir "${PROJECT_BINARY_DIR}/python")
configure_package_config_file("${CMAKE_CURRENT_LIST_DIR}/TrickConfig.cmake.in"
    "${PROJECT_BINARY_DIR}/package/TrickConfig.cmake"
    INSTALL_DESTINATION "${PROJECT_BINARY_DIR}/package"
    INSTALL_PREFIX "${PROJECT_BINARY_DIR}" PATH_VARS trick_package_python_dir)
write_basic_package_version_file("${PROJECT_BINARY_DIR}/package/TrickConfigVersion.cmake"
    VERSION "${PROJECT_VERSION}" COMPATIBILITY SameMinorVersion)
configure_file("${CMAKE_CURRENT_LIST_DIR}/modules/FindUDUNITS2.cmake"
    "${PROJECT_BINARY_DIR}/package/FindUDUNITS2.cmake" COPYONLY)
configure_file("${CMAKE_CURRENT_LIST_DIR}/TrickRuntime.cmake"
    "${PROJECT_BINARY_DIR}/package/TrickRuntime.cmake" COPYONLY)
install(FILES "${PROJECT_BINARY_DIR}/install-package/TrickConfig.cmake"
    "${PROJECT_BINARY_DIR}/package/TrickConfigVersion.cmake"
    "${PROJECT_BINARY_DIR}/package/FindUDUNITS2.cmake"
    "${PROJECT_BINARY_DIR}/package/TrickRuntime.cmake" DESTINATION "${trick_package_dir}")
install(FILES "${PROJECT_BINARY_DIR}/python/trick/__init__.py" DESTINATION share/trick/swig/trick)

install(DIRECTORY cmake/examples/consumer DESTINATION share/trick/examples)
list(GET ${python_package}_INCLUDE_DIRS 0 sdk_python_include)
file(GENERATE OUTPUT "${PROJECT_BINARY_DIR}/package-consumer-hints.cmake" CONTENT
    "set(UDUNITS2_INCLUDE_DIR \"${UDUNITS2_INCLUDE_DIR}\" CACHE PATH \"\")\nset(UDUNITS2_LIBRARY \"${UDUNITS2_LIBRARY}\" CACHE FILEPATH \"\")\nset(${python_package}_INCLUDE_DIR \"${sdk_python_include}\" CACHE PATH \"\")\nset(${python_package}_LIBRARY \"$<TARGET_FILE:Trick::Python>\" CACHE FILEPATH \"\")\n")
install(FILES cmake/tests/Package.cmake DESTINATION share/trick/tests)
if(BUILD_TESTING)
    add_test(NAME sdk.package COMMAND "${CMAKE_COMMAND}"
        "-DPACKAGE_ROOT=${PROJECT_BINARY_DIR}/package"
        "-DCONSUMER=${PROJECT_SOURCE_DIR}/cmake/examples/consumer"
        "-DHINTS=${PROJECT_BINARY_DIR}/package-consumer-hints.cmake"
        "-DTEST_ROOT=${PROJECT_BINARY_DIR}/sdk-tests/$<CONFIG>/package"
        -P "${PROJECT_SOURCE_DIR}/cmake/tests/Package.cmake")
    set_tests_properties(sdk.package PROPERTIES LABELS sdk TIMEOUT 180)
endif()
