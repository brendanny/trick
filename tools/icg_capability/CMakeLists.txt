cmake_minimum_required(VERSION 3.16)
project(trick_icg_libclang17_probe LANGUAGES CXX)

set(LLVM_ROOT "" CACHE PATH "LLVM 17 installation prefix")
if(NOT LLVM_ROOT)
    message(FATAL_ERROR "Set LLVM_ROOT to the LLVM 17 installation prefix")
endif()

find_path(LIBCLANG_INCLUDE_DIR clang-c/Index.h
    HINTS "${LLVM_ROOT}/include"
    NO_DEFAULT_PATH
    REQUIRED)
find_library(LIBCLANG_LIBRARY NAMES clang libclang
    HINTS "${LLVM_ROOT}/lib" "${LLVM_ROOT}/lib64"
    NO_DEFAULT_PATH
    REQUIRED)

add_executable(libclang17_probe libclang17_probe.cpp)
target_compile_features(libclang17_probe PRIVATE cxx_std_17)
target_compile_options(libclang17_probe PRIVATE -Wall -Wextra -Wpedantic)
target_include_directories(libclang17_probe PRIVATE "${LIBCLANG_INCLUDE_DIR}")
target_link_libraries(libclang17_probe PRIVATE "${LIBCLANG_LIBRARY}")

enable_testing()
add_test(NAME libclang17_capabilities
    COMMAND libclang17_probe "${CMAKE_CURRENT_SOURCE_DIR}/fixture.hh")
