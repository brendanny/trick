include("${CMAKE_CURRENT_LIST_DIR}/TrickSDKSourceLinks.cmake")
trick_check_sdk_source_links("${PROJECT_SOURCE_DIR}")

# Explicit core SDK artifact families. Optional native/Java tools join in D.
set_target_properties(trick-ICG PROPERTIES INSTALL_RPATH_USE_LINK_PATH ON)
install(TARGETS ${trick_sdk_archives} trick-ICG EXPORT TrickTargets
    ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
    RUNTIME DESTINATION bin)
install(PROGRAMS bin/trick-CP bin/trick-config bin/trick-gte bin/trick-ify
    bin/trick-killsim bin/trick-units bin/trick-version DESTINATION bin)
install(DIRECTORY include/ DESTINATION include)
set(sdk_er7_exclude)
if(NOT TRICK_USE_ER7_UTILS)
    list(APPEND sdk_er7_exclude PATTERN "er7_utils" EXCLUDE)
endif()
install(DIRECTORY trick_source/ DESTINATION trick_source
    FILES_MATCHING PATTERN "*.h" PATTERN "*.hh" PATTERN "*.hpp" PATTERN "*.ipp"
    PATTERN "test" EXCLUDE PATTERN "tests" EXCLUDE ${sdk_er7_exclude})
install(DIRECTORY libexec/trick DESTINATION libexec USE_SOURCE_PERMISSIONS
    PATTERN "__pycache__" EXCLUDE)
install(DIRECTORY share/trick DESTINATION share USE_SOURCE_PERMISSIONS
    PATTERN "config_user.mk" EXCLUDE PATTERN "__pycache__" EXCLUDE
    PATTERN "trickops/README.md" EXCLUDE)
# Materialize the source README symlink whose target is outside share/trick.
install(FILES docs/documentation/miscellaneous_trick_tools/TrickOps.md
    DESTINATION share/trick/trickops RENAME README.md)
install(FILES "${PROJECT_BINARY_DIR}/sdk-config/$<CONFIG>/config_user.mk"
    "${PROJECT_BINARY_DIR}/sdk-config/$<CONFIG>/cmake-sdk.mk"
    DESTINATION share/trick/makefiles)
install(FILES "${PROJECT_BINARY_DIR}/sdk-model-predefines.txt"
    DESTINATION share/trick RENAME model-predefines.txt)
install(FILES "${PROJECT_BINARY_DIR}/sdk-config/$<CONFIG>/sdk.env" DESTINATION share/trick)
install(FILES "${PROJECT_BINARY_DIR}/trick_source/sim_services/metadata/$<CONFIG>/classes.resource"
    DESTINATION share/trick/xml RENAME sim_services_classes.resource)
foreach(module IN ITEMS sim_services swig_double swig_int swig_ref)
    install(FILES "${PROJECT_BINARY_DIR}/python/${module}.py" DESTINATION share/trick/swig)
endforeach()
install(DIRECTORY cmake/examples/SIM_sdk DESTINATION share/trick/examples
    PATTERN "__pycache__" EXCLUDE)
install(FILES cmake/tests/SDK.cmake DESTINATION share/trick/tests)
install(FILES LICENSE DESTINATION share/licenses/trick)
