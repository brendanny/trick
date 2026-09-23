trick_service(trick_pyip PythonInput)
target_sources(trick_pyip PRIVATE
    IPPython.cpp
    IPPythonEvent.cpp
    InputProcessor.cpp
    MTV.cpp
    MTV_c_intf.cpp
    input_processor_ext.cpp
    ../../trick_swig/PrimitiveAttributesMap.cpp
    ../../trick_swig/swig_convert_units.cpp
    ../../trick_swig/swig_global_vars.cpp
)
target_link_libraries(trick_pyip PUBLIC Trick::Core Trick::Python PRIVATE Trick::MemorySupport)
# Core services call the input processor. LINK_ONLY keeps Python include flags
# off unrelated core compilation while declaring the real static link cycle.
target_link_libraries(trick_core PRIVATE "$<LINK_ONLY:trick_pyip>")
add_subdirectory("${PROJECT_SOURCE_DIR}/trick_source/trick_swig" "${PROJECT_BINARY_DIR}/trick_source/trick_swig")

# Registration is a separate entry point; simulation-generated init_swig_modules
# remains available to legacy consumers and will be integrated by C1.
add_library(trick_python_registration STATIC "${PROJECT_SOURCE_DIR}/cmake/TrickPythonRegistration.cpp")
target_link_libraries(trick_python_registration PUBLIC Trick::PythonInput)
foreach(module IN ITEMS sim_services swig_double swig_int swig_ref)
    target_link_libraries(trick_python_registration PUBLIC trick_swig_${module})
    add_dependencies(trick_python_registration trick_${module}_proxy)
endforeach()
add_library(trick_runtime INTERFACE)
add_library(Trick::Runtime ALIAS trick_runtime)
target_link_libraries(trick_runtime INTERFACE trick_python_registration Trick::Core Trick::MemorySupport
    "$<LINK_LIBRARY:WHOLE_ARCHIVE,trick_core_metadata>")
# MemoryManager's named allocators are discovered with dlsym in the executable.
function(trick_enable_runtime target)
    target_link_libraries(${target} PRIVATE Trick::Runtime)
    set_target_properties(${target} PROPERTIES ENABLE_EXPORTS ON)
endfunction()

if(BUILD_TESTING)
    add_executable(trick_python_unicode "${PROJECT_SOURCE_DIR}/trick_source/trick_swig/tests/PythonUnicode.cpp")
    target_compile_features(trick_python_unicode PRIVATE cxx_std_17)
    target_include_directories(trick_python_unicode PRIVATE "${PROJECT_SOURCE_DIR}/include")
    target_link_libraries(trick_python_unicode PRIVATE Trick::Python)
    add_test(NAME runtime.python_unicode COMMAND trick_python_unicode)
    set_tests_properties(runtime.python_unicode PROPERTIES LABELS "runtime;python")
    add_executable(trick_python_smoke "${PROJECT_SOURCE_DIR}/cmake/tests/PythonInput.cpp")
    trick_enable_runtime(trick_python_smoke)
    add_test(NAME runtime.python_input COMMAND trick_python_smoke)
    file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/startup_input.py" "trick_startup_input_ran = True\n")
    add_test(NAME runtime.python_input_unset_path COMMAND trick_python_smoke
        "${CMAKE_CURRENT_BINARY_DIR}/startup_input.py")
    add_test(NAME runtime.python_input_empty_path COMMAND trick_python_smoke
        "${CMAKE_CURRENT_BINARY_DIR}/startup_input.py")
    set(path_fixture "${CMAKE_CURRENT_BINARY_DIR}/path-fixture")
    file(MAKE_DIRECTORY "${path_fixture}/first" "${path_fixture}/second")
    file(WRITE "${path_fixture}/first/trick_path_probe.py" "origin = 'first'\n")
    file(WRITE "${path_fixture}/second/trick_path_probe.py" "origin = 'second'\n")
    file(WRITE "${path_fixture}/second/trick_second_path_probe.py" "present = True\n")
    file(WRITE "${path_fixture}/input.py"
        "import trick_path_probe, trick_second_path_probe\nassert trick_path_probe.origin == 'first'\nassert trick_second_path_probe.present\ntrick_startup_input_ran = True\n")
    add_test(NAME runtime.python_input_path_entries COMMAND trick_python_smoke "${path_fixture}/input.py")
    add_test(NAME runtime.python_startup_failure COMMAND trick_python_smoke
        "${CMAKE_CURRENT_BINARY_DIR}/startup_input.py" expect-startup-failure)
    set_tests_properties(runtime.python_input runtime.python_input_unset_path runtime.python_input_empty_path
        runtime.python_input_path_entries runtime.python_startup_failure
        PROPERTIES LABELS "runtime;python" TIMEOUT 120
        ENVIRONMENT "PYTHONPATH=${TRICK_PYTHON_STAGE};TRICK_HOME=${PROJECT_SOURCE_DIR};TRICK_PYTHON_PATH=${TRICK_PYTHON_STAGE};PYTHONDONTWRITEBYTECODE=1")
    set_tests_properties(runtime.python_input_unset_path PROPERTIES
        ENVIRONMENT_MODIFICATION "TRICK_PYTHON_PATH=unset:")
    set_tests_properties(runtime.python_input_empty_path PROPERTIES
        ENVIRONMENT_MODIFICATION "TRICK_PYTHON_PATH=set:")
    set_tests_properties(runtime.python_input_path_entries PROPERTIES
        ENVIRONMENT_MODIFICATION "TRICK_PYTHON_PATH=set:: ${path_fixture}/first :: \t : ${path_fixture}/second :")
    set_tests_properties(runtime.python_startup_failure PROPERTIES
        ENVIRONMENT_MODIFICATION "TRICK_HOME=unset:")
endif()
