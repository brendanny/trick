set(MSD_ROOT ${TRICK_ROOT}/trick_sims/SIM_msd)
set(MSD_INCLUDE ${MSD_ROOT}/models/msd/include)
set(GENERATED ${CMAKE_CURRENT_BINARY_DIR}/generated)
add_custom_command(OUTPUT ${GENERATED}/metadata.cpp ${GENERATED}/bindings.cpp ${GENERATED}/generated.hh ${GENERATED}/declarations.json
  COMMAND ${Python_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/generate.py
    --header ${CMAKE_CURRENT_SOURCE_DIR}/models.hh
    --policy ${CMAKE_CURRENT_SOURCE_DIR}/policy.json --output ${GENERATED}
    --compiler ${CMAKE_CXX_COMPILER}
    -I ${MSD_INCLUDE} -I ${TRICK_ROOT}/include -I ${UDUNITS_INCLUDE}
  DEPENDS generate.py policy.json models.hh ${MSD_INCLUDE}/msd.hh
  VERBATIM)
add_custom_target(integration_generate DEPENDS ${GENERATED}/generated.hh ${GENERATED}/bindings.cpp)
file(GLOB MSD_SOURCES CONFIGURE_DEPENDS ${MSD_ROOT}/models/msd/src/*.cpp)
add_library(integration_models SHARED models.cpp ${GENERATED}/metadata.cpp ${MSD_SOURCES}
  ${SERVICES}/CheckPointRestart/stl_type_name_convert.cpp
  ${SERVICES}/Integrator/src/Integrator.cpp
  ${SERVICES}/Integrator/src/Integrator_C_Intf.cpp
  ${SERVICES}/Integrator/trick_algorithms/RK4_Integrator.cpp)
target_include_directories(integration_models PUBLIC ${CMAKE_CURRENT_SOURCE_DIR} ${MSD_INCLUDE} ${GENERATED})
target_link_libraries(integration_models PUBLIC poc_fixture)
# This pointer is supplied by the small driver, as it is by Trick's integration
# scheduler in a full simulation. No substitute numerical algorithm is used.
add_library(integration_runtime SHARED runtime.cpp)
target_link_libraries(integration_runtime PUBLIC integration_models)
pybind11_add_module(_msd_consumer consumer.cpp)
target_link_libraries(_msd_consumer PRIVATE integration_runtime)
add_executable(poc_msd main.cpp module.cpp ${GENERATED}/bindings.cpp
  ${SERVICES}/InputProcessor/InputProcessor.cpp
  ${SERVICES}/InputProcessor/IPPython.cpp)
target_link_libraries(poc_msd PRIVATE integration_runtime pybind11::embed pthread)
target_link_options(poc_msd PRIVATE -Wl,--export-dynamic)
add_dependencies(poc_msd integration_generate _msd_consumer)
add_test(NAME integration_generator COMMAND ${Python_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_generator.py)
add_test(NAME integration_msd COMMAND ${Python_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/run.py
  --build-dir ${CMAKE_BINARY_DIR})
set_tests_properties(integration_msd PROPERTIES TIMEOUT 60)
