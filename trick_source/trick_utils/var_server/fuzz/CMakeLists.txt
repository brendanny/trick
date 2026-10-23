# libFuzzer targets for libtrick_var_server. Clang only.
if(NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    message(FATAL_ERROR "TRICK_VS_FUZZ needs Clang (libFuzzer)")
endif()

set(_vs_fuzz_flags -fsanitize=fuzzer,address,undefined -fno-sanitize-recover=undefined -fno-omit-frame-pointer)

# The library itself is built again with coverage and sanitizers for the fuzzer.
get_filename_component(_vs_dir "${CMAKE_CURRENT_SOURCE_DIR}/.." ABSOLUTE)
get_filename_component(_vs_trick_root "${_vs_dir}/../../.." ABSOLUTE)
set(_vs_fuzz_sources ${TRICK_VS_SOURCES})
list(TRANSFORM _vs_fuzz_sources PREPEND "${_vs_dir}/")
add_library(trick_var_server_fuzzlib STATIC ${_vs_fuzz_sources})
target_include_directories(trick_var_server_fuzzlib PUBLIC "${_vs_trick_root}/include")
target_compile_features(trick_var_server_fuzzlib PUBLIC cxx_std_17)
target_compile_options(trick_var_server_fuzzlib PRIVATE -fsanitize=fuzzer-no-link,address,undefined
    -fno-sanitize-recover=undefined -fno-omit-frame-pointer)

add_executable(vs_command_parser_fuzz CommandParser_fuzz.cpp)
target_link_libraries(vs_command_parser_fuzz PRIVATE trick_var_server_fuzzlib)
target_compile_options(vs_command_parser_fuzz PRIVATE ${_vs_fuzz_flags})
target_link_options(vs_command_parser_fuzz PRIVATE ${_vs_fuzz_flags})

add_executable(vs_encoders_fuzz Encoders_fuzz.cpp)
target_link_libraries(vs_encoders_fuzz PRIVATE trick_var_server_fuzzlib)
target_compile_options(vs_encoders_fuzz PRIVATE ${_vs_fuzz_flags})
target_link_options(vs_encoders_fuzz PRIVATE ${_vs_fuzz_flags})

add_executable(vs_line_reader_fuzz LineReader_fuzz.cpp)
target_link_libraries(vs_line_reader_fuzz PRIVATE trick_var_server_fuzzlib)
target_compile_options(vs_line_reader_fuzz PRIVATE ${_vs_fuzz_flags})
target_link_options(vs_line_reader_fuzz PRIVATE ${_vs_fuzz_flags})
