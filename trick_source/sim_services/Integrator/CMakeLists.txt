# Scheduler/SimObject integration sources join Core in B5; algorithms have one
# owner here. Feature definitions propagate to users of the public headers.
trick_service(trick_integrators Integrators)
target_include_directories(trick_integrators PUBLIC
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/trick_source>"
    "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include/trick/compat>"
    "$<INSTALL_INTERFACE:include/trick/compat>"
    "$<INSTALL_INTERFACE:trick_source>")
target_sources(trick_integrators PRIVATE
    src/Integrator.cpp
    src/getIntegrator.cpp
    src/regula_falsi.c
    src/reset_regula_falsi.c
)
target_link_libraries(trick_integrators PUBLIC Trick::MemoryManager)
if(TRICK_USE_ER7_UTILS)
    target_compile_definitions(trick_integrators PUBLIC USE_ER7_UTILS_INTEGRATORS)
    add_subdirectory("${PROJECT_SOURCE_DIR}/trick_source/er7_utils" "${PROJECT_BINARY_DIR}/trick_source/er7_utils")
    target_link_libraries(trick_integrators PUBLIC Trick::Er7Utils)
else()
    target_sources(trick_integrators PRIVATE
        trick_algorithms/ABM_Integrator.cpp
        trick_algorithms/Euler_Cromer_Integrator.cpp
        trick_algorithms/Euler_Integrator.cpp
        trick_algorithms/MM4_Integrator.cpp
        trick_algorithms/NL2_Integrator.cpp
        trick_algorithms/RK2_Integrator.cpp
        trick_algorithms/RK4_Integrator.cpp
        trick_algorithms/RKF45_Integrator.cpp
        trick_algorithms/RKF78_Integrator.cpp
        trick_algorithms/RKG4_Integrator.cpp
    )
endif()
if(BUILD_TESTING)
    add_executable(trick_integrators_smoke "${PROJECT_SOURCE_DIR}/cmake/tests/Integrators.cpp"
        "${PROJECT_SOURCE_DIR}/cmake/tests/MessageSink.cpp")
    target_link_libraries(trick_integrators_smoke PRIVATE Trick::Integrators)
    add_test(NAME runtime.integrators COMMAND trick_integrators_smoke)
    set_tests_properties(runtime.integrators PROPERTIES LABELS "runtime;integrators")
endif()
