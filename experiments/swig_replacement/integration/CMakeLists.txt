set(MSD_ROOT ${TRICK_ROOT}/trick_sims/SIM_msd)
set(MSD_INCLUDE ${MSD_ROOT}/models/msd/include)
set(GENERATED ${CMAKE_CURRENT_BINARY_DIR}/generated)
add_custom_command(OUTPUT ${GENERATED}/metadata.cpp ${GENERATED}/bindings.cpp ${GENERATED}/generated.hh ${GENERATED}/declarations.json
  COMMAND ${Python_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/generate.py
    --header ${CMAKE_CURRENT_SOURCE_DIR}/models.hh
    --policy ${CMAKE_CURRENT_SOURCE_DIR}/policy.json --output ${GENERATED}
    --compiler ${CMAKE_CXX_COMPILER} --backend ${POC_INTEGRATION_BACKEND}
    -I ${MSD_INCLUDE} -I ${TRICK_ROOT}/include -I ${UDUNITS_INCLUDE}
  DEPENDS generate.py emit_boost.py policy.json models.hh ${MSD_INCLUDE}/msd.hh
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
if(POC_INTEGRATION_BACKEND STREQUAL "boost")
  # One shared conversion registry must serve the builtin and consumer modules.
  if(Boost_USE_STATIC_LIBS)
    message(FATAL_ERROR "The Boost.Python integration experiment requires shared Boost libraries")
  endif()
  set(Boost_USE_STATIC_LIBS OFF)
  set(Boost_PYTHON_VERSION "${Python_VERSION_MAJOR}.${Python_VERSION_MINOR}")
  find_package(Boost 1.70 CONFIG REQUIRED COMPONENTS python)
  if(Boost_VERSION VERSION_LESS 1.87)
    message(WARNING "Boost.Python before 1.87 lacks an upstream holder alignment fix. This experiment permits older versions to reproduce the sanitizer failure; see BOOST_PYTHON.md.")
  endif()
  get_target_property(BOOST_PYTHON_TYPE Boost::python TYPE)
  if(NOT BOOST_PYTHON_TYPE STREQUAL "SHARED_LIBRARY")
    message(FATAL_ERROR "Boost::python must be a shared library")
  endif()
  Python_add_library(_msd_consumer MODULE WITH_SOABI boost_consumer.cpp)
  target_link_libraries(_msd_consumer PRIVATE Boost::python)
  set(BINDING_MODULE boost_module.cpp)
  set(BINDING_LIBRARY Boost::python Python::Python)
  set(BINDING_VERSION ${Boost_VERSION})
  set(BINDING_RUNTIME "$<TARGET_FILE:Boost::python>")
else()
  pybind11_add_module(_msd_consumer consumer.cpp)
  set(BINDING_MODULE module.cpp)
  set(BINDING_LIBRARY pybind11::embed)
  set(BINDING_VERSION ${pybind11_VERSION})
  set(BINDING_RUNTIME "")
endif()
file(GENERATE OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/binding-build.json CONTENT
  "{\"backend\":\"${POC_INTEGRATION_BACKEND}\",\"version\":\"${BINDING_VERSION}\",\"library\":\"${BINDING_RUNTIME}\"}\n")
target_link_libraries(_msd_consumer PRIVATE integration_runtime)
add_executable(poc_msd main.cpp ${BINDING_MODULE} ${GENERATED}/bindings.cpp
  ${SERVICES}/InputProcessor/InputProcessor.cpp
  ${SERVICES}/InputProcessor/IPPython.cpp)
target_link_libraries(poc_msd PRIVATE integration_runtime ${BINDING_LIBRARY} pthread)
if(POC_INTEGRATION_BACKEND STREQUAL "boost")
  # An isolated UDUNITS prefix can also contain an older Boost installation.
  # Keep the selected Boost headers ahead of those transitive include paths.
  foreach(target poc_msd _msd_consumer)
    set_property(TARGET ${target} PROPERTY NO_SYSTEM_FROM_IMPORTED TRUE)
    target_include_directories(${target} BEFORE PRIVATE $<TARGET_PROPERTY:Boost::python,INTERFACE_INCLUDE_DIRECTORIES>)
  endforeach()
endif()
target_link_options(poc_msd PRIVATE -Wl,--export-dynamic)
add_dependencies(poc_msd integration_generate _msd_consumer)
add_test(NAME integration_generator COMMAND ${Python_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_generator.py)
add_test(NAME integration_msd COMMAND ${Python_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/run.py
  --build-dir ${CMAKE_BINARY_DIR})
set_tests_properties(integration_msd PROPERTIES TIMEOUT 60)
