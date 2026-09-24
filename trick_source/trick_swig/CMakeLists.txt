include(UseSWIG)
# Separate module output directories prevent one SWIG invocation from removing
# another module's support files. Copy the proxies into a common import directory.
set(UseSWIG_MODULE_VERSION 2)
set(TRICK_PYTHON_STAGE "${PROJECT_BINARY_DIR}/python" PARENT_SCOPE)
set(python_stage "${PROJECT_BINARY_DIR}/python")
file(MAKE_DIRECTORY "${python_stage}/trick")
configure_file("${PROJECT_SOURCE_DIR}/cmake/trick-python-init.py.in" "${python_stage}/trick/__init__.py" COPYONLY)
foreach(module IN ITEMS sim_services swig_double swig_int swig_ref)
    set_source_files_properties("${module}.i" PROPERTIES CPLUSPLUS ON
        USE_SWIG_DEPENDENCIES TRUE SWIG_MODULE_NAME "${module}"
        COMPILE_OPTIONS "-includeall;-ignoremissing;-w201,362,389,451;-interface;_${module}")
    swig_add_library(trick_swig_${module} TYPE STATIC LANGUAGE python
        OUTPUT_DIR "${CMAKE_CURRENT_BINARY_DIR}/${module}/python"
        OUTFILE_DIR "${CMAKE_CURRENT_BINARY_DIR}/${module}/wrapper"
        SOURCES "${module}.i")
    set_target_properties(trick_swig_${module} PROPERTIES
        SWIG_USE_TARGET_INCLUDE_DIRECTORIES FALSE POSITION_INDEPENDENT_CODE ON
        SWIG_INCLUDE_DIRECTORIES "${PROJECT_SOURCE_DIR}/include;${PROJECT_SOURCE_DIR}/trick_source;${PROJECT_SOURCE_DIR}")
    set_target_properties(trick_swig_${module} PROPERTIES
        CXX_EXTENSIONS OFF)
    target_include_directories(trick_swig_${module} PRIVATE
        "${PROJECT_SOURCE_DIR}/include" "${PROJECT_SOURCE_DIR}/trick_source" "${PROJECT_SOURCE_DIR}")
    target_compile_features(trick_swig_${module} PRIVATE cxx_std_17)
    target_link_libraries(trick_swig_${module} PUBLIC Trick::PythonInput PRIVATE Trick::MemorySupport)
    set_property(TARGET trick_swig_${module} PROPERTY SWIG_COMPILE_DEFINITIONS
        TRICK_VER=${PROJECT_VERSION_MAJOR} TRICK_MINOR=${PROJECT_VERSION_MINOR})
    if(TRICK_USE_ER7_UTILS)
        set_property(TARGET trick_swig_${module} APPEND PROPERTY SWIG_COMPILE_DEFINITIONS USE_ER7_UTILS_INTEGRATORS)
    endif()
    add_custom_command(OUTPUT "${python_stage}/${module}.py"
        COMMAND "${CMAKE_COMMAND}" -E copy_if_different
            "${CMAKE_CURRENT_BINARY_DIR}/${module}/python/${module}.py" "${python_stage}/${module}.py"
        DEPENDS "${CMAKE_CURRENT_BINARY_DIR}/${module}/python/${module}.py"
        VERBATIM)
    add_custom_target(trick_${module}_proxy ALL DEPENDS "${python_stage}/${module}.py")
    add_dependencies(trick_${module}_proxy trick_swig_${module})
endforeach()
