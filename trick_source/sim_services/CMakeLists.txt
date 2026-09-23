# Each source and generated object has one owning target.
function(trick_service target alias)
    add_library(${target} STATIC)
    add_library(Trick::${alias} ALIAS ${target})
    target_compile_features(${target} PUBLIC cxx_std_17)
    target_compile_definitions(${target} PUBLIC TRICK_VER=${PROJECT_VERSION_MAJOR} TRICK_MINOR=${PROJECT_VERSION_MINOR})
    target_include_directories(${target} PUBLIC "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>")
    set_target_properties(${target} PROPERTIES POSITION_INDEPENDENT_CODE ON CXX_EXTENSIONS OFF)
endfunction()

if(TRICK_BUILD_MEMORY_MANAGER)
    add_subdirectory(MemoryManager)
endif()

if(TRICK_BUILD_INTEGRATORS)
    add_subdirectory(Integrator)
endif()

if(TRICK_BUILD_CORE_METADATA)
    include("${PROJECT_SOURCE_DIR}/cmake/TrickCoreCodegen.cmake")
endif()
