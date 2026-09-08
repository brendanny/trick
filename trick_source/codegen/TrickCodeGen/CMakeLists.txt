cmake_minimum_required(VERSION 3.20)
project(trick_icg_extract VERSION 0.10.0 LANGUAGES C CXX)

# Deliberately standalone: the legacy ICG remains the production build path.
find_package(LLVM REQUIRED CONFIG)
if(LLVM_VERSION_MAJOR LESS 17 OR LLVM_VERSION_MAJOR GREATER 23)
    message(FATAL_ERROR "Supported LLVM/Clang majors are 17 through 23")
endif()
find_package(Clang REQUIRED CONFIG HINTS "${LLVM_DIR}/../clang" NO_DEFAULT_PATH)
find_program(ICG_CLANG_EXECUTABLE NAMES clang
    HINTS "${LLVM_TOOLS_BINARY_DIR}" NO_DEFAULT_PATH REQUIRED)
execute_process(COMMAND "${ICG_CLANG_EXECUTABLE}" -dumpversion
    RESULT_VARIABLE version_result OUTPUT_VARIABLE clang_version
    OUTPUT_STRIP_TRAILING_WHITESPACE)
if(NOT version_result EQUAL 0 OR NOT clang_version MATCHES "^${LLVM_VERSION_MAJOR}\\.")
    message(FATAL_ERROR "Clang executable does not match LLVM ${LLVM_VERSION_MAJOR}: ${clang_version}")
endif()
execute_process(COMMAND "${ICG_CLANG_EXECUTABLE}" -print-resource-dir
    RESULT_VARIABLE resource_result OUTPUT_VARIABLE ICG_RESOURCE_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE)
if(NOT resource_result EQUAL 0 OR NOT EXISTS "${ICG_RESOURCE_DIR}/include/stddef.h")
    message(FATAL_ERROR "Cannot discover the matching Clang resource headers")
endif()
configure_file(extractor/Config.hh.in generated/Config.hh @ONLY)

add_executable(trick-icg-extract extractor/main.cpp extractor/Facts.cpp
    extractor/TypeNode.cpp extractor/TypeGraph.cpp extractor/DeclarationIdentity.cpp extractor/TemplateFacts.cpp)
set_target_properties(trick-icg-extract PROPERTIES
    CXX_STANDARD 17 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO)
target_include_directories(trick-icg-extract SYSTEM PRIVATE
    ${LLVM_INCLUDE_DIRS} ${CLANG_INCLUDE_DIRS})
target_include_directories(trick-icg-extract PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/generated")
target_compile_options(trick-icg-extract PRIVATE -Wall -Wextra -Wpedantic)
if(NOT LLVM_ENABLE_RTTI)
    target_compile_options(trick-icg-extract PRIVATE -fno-rtti)
endif()
# RHEL/Rocky ship the combined C++ library without the component archives.
# Respect the package's supported linkage instead of inventing -lclangTooling.
set(ICG_CLANG_LINKAGE AUTO CACHE STRING "Clang linkage: AUTO, SHARED, or COMPONENTS")
set_property(CACHE ICG_CLANG_LINKAGE PROPERTY STRINGS AUTO SHARED COMPONENTS)
if(NOT ICG_CLANG_LINKAGE MATCHES "^(AUTO|SHARED|COMPONENTS)$")
    message(FATAL_ERROR "Invalid ICG_CLANG_LINKAGE: ${ICG_CLANG_LINKAGE}")
endif()
if(ICG_CLANG_LINKAGE STREQUAL "SHARED" OR
   (ICG_CLANG_LINKAGE STREQUAL "AUTO" AND CLANG_LINK_CLANG_DYLIB AND TARGET clang-cpp))
    target_link_libraries(trick-icg-extract PRIVATE clang-cpp LLVM)
else()
    target_link_libraries(trick-icg-extract PRIVATE clangTooling clangIndex)
endif()

include(CTest)
if(BUILD_TESTING)
    option(ICG_TEST_LIFECYCLE_SANITIZERS "Run lifecycle probes with ASan/UBSan/LSan on Linux" OFF)
    find_package(Python3 3.11 REQUIRED COMPONENTS Interpreter)
    add_executable(icg-compat-test tests/test_compat.cpp)
    set_target_properties(icg-compat-test PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED YES)
    target_include_directories(icg-compat-test SYSTEM PRIVATE ${LLVM_INCLUDE_DIRS} ${CLANG_INCLUDE_DIRS})
    target_include_directories(icg-compat-test PRIVATE extractor "${CMAKE_CURRENT_BINARY_DIR}/generated")
    get_target_property(ICG_TEST_LINK_LIBRARIES trick-icg-extract LINK_LIBRARIES)
    target_link_libraries(icg-compat-test PRIVATE ${ICG_TEST_LINK_LIBRARIES})
    add_test(NAME icg_compat_invalid_linkage COMMAND icg-compat-test)
    # Homebrew's stddef.h goes through libc++ wrappers outside the resource dir.
    # Map that separate root explicitly in tests, as a caller must do in practice.
    set(ICG_TEST_ROOT_ARGS "")
    foreach(include_dir IN LISTS LLVM_INCLUDE_DIRS)
        if(EXISTS "${include_dir}/c++/v1/stddef.h")
            list(APPEND ICG_TEST_ROOT_ARGS --path-root "stdlib=${include_dir}/c++/v1")
            break()
        endif()
    endforeach()
    if(ICG_TEST_LIFECYCLE_SANITIZERS)
        if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux")
            message(FATAL_ERROR "The lifecycle leak-check lane requires Linux")
        endif()
        list(APPEND ICG_TEST_ROOT_ARGS --lifecycle-leak-check)
    endif()
    add_test(NAME icg_extract_integration
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_extract.py"
            --extractor "$<TARGET_FILE:trick-icg-extract>"
            --llvm-major "${LLVM_VERSION_MAJOR}"
            --layout-compiler "${CMAKE_CXX_COMPILER}" ${ICG_TEST_ROOT_ARGS})
endif()
