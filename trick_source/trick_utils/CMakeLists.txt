# Native utility archives; no generated SDK or framework Make configuration required.
find_package(Threads REQUIRED)

function(trick_utility target alias)
    add_library(${target} STATIC)
    add_library(Trick::${alias} ALIAS ${target})
    set_target_properties(${target} PROPERTIES EXPORT_NAME "${alias}")
    target_include_directories(${target} PUBLIC
        "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>" "$<INSTALL_INTERFACE:include>")
    set_target_properties(${target} PROPERTIES POSITION_INDEPENDENT_CODE ON CXX_EXTENSIONS OFF)
    target_compile_options(${target} PRIVATE
        "$<$<COMPILE_LANG_AND_ID:C,GNU,Clang,AppleClang>:-Wall;-Wextra;-fexceptions>"
        "$<$<COMPILE_LANG_AND_ID:CXX,GNU,Clang,AppleClang>:-Wall;-Wextra>")
endfunction()

add_subdirectory(math)
add_subdirectory(units)
add_subdirectory(comm)
add_subdirectory(connection_handlers)
add_subdirectory(optimization)
add_subdirectory(var_binary_parser)

if(BUILD_TESTING AND TRICK_BUILD_UTILITY_TESTS)
    add_subdirectory(tests)
endif()
