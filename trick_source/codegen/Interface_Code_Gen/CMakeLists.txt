# The existing ICG frontend; the separate rewrite is not part of this migration.
add_executable(trick-ICG
    ClassTemplateVisitor.cpp
    ClassValues.cpp
    ClassVisitor.cpp
    CommentSaver.cpp
    ConstructValues.cpp
    EnumValues.cpp
    EnumVisitor.cpp
    FieldDescription.cpp
    FieldVisitor.cpp
    FindTrickICG.cpp
    HeaderSearchDirs.cpp
    ICGASTConsumer.cpp
    ICGDiagnosticConsumer.cpp
    PrintAttributes.cpp
    PrintFileContents10.cpp
    PrintFileContentsBase.cpp
    TranslationUnitVisitor.cpp
    TypedefVisitor.cpp
    Utilities.cpp
    VariableVisitor.cpp
    main.cpp
    ../../sim_services/UdUnits/map_trick_units_to_udunits.cpp
)
add_executable(Trick::ICG ALIAS trick-ICG)
target_compile_features(trick-ICG PRIVATE cxx_std_17)
set_target_properties(trick-ICG PROPERTIES CXX_EXTENSIONS OFF)
target_include_directories(trick-ICG PRIVATE "${PROJECT_SOURCE_DIR}/include" "${CMAKE_CURRENT_BINARY_DIR}")
target_include_directories(trick-ICG SYSTEM PRIVATE ${LLVM_INCLUDE_DIRS} ${CLANG_INCLUDE_DIRS})
string(REPLACE ";" " " llvm_definition_flags "${LLVM_DEFINITIONS}")
separate_arguments(llvm_definition_flags NATIVE_COMMAND "${llvm_definition_flags}")
target_compile_options(trick-ICG PRIVATE ${llvm_definition_flags})
if(NOT LLVM_ENABLE_RTTI)
    target_compile_options(trick-ICG PRIVATE "$<$<CXX_COMPILER_ID:GNU,Clang,AppleClang>:-fno-rtti>")
endif()
target_compile_definitions(trick-ICG PRIVATE
    TRICK_ICG_CMAKE_CONFIG
    LIBCLANG_MAJOR=${LLVM_VERSION_MAJOR}
    LIBCLANG_MINOR=${LLVM_VERSION_MINOR}
    LIBCLANG_PATCHLEVEL=${LLVM_VERSION_PATCH}
    TRICK_VERSION="${TRICK_VERSION}")
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    target_compile_definitions(trick-ICG PRIVATE TRICK_GCC_VERSION="${CMAKE_CXX_COMPILER_VERSION}")
endif()
if(TARGET clang-cpp AND TARGET LLVM)
    target_link_libraries(trick-ICG PRIVATE clang-cpp LLVM)
else()
    # Config targets carry their component dependencies and platform system libs.
    target_link_libraries(trick-ICG PRIVATE clangFrontend clangParse clangSema clangAST clangLex clangBasic)
endif()
target_link_libraries(trick-ICG PRIVATE UDUNITS2::UDUNITS2)

# Query the Clang executable belonging to the selected development package.
find_program(TRICK_ICG_CLANG_EXECUTABLE NAMES clang
    PATHS "${LLVM_TOOLS_BINARY_DIR}" NO_DEFAULT_PATH REQUIRED)
file(REAL_PATH "${LLVM_TOOLS_BINARY_DIR}" llvm_tools_dir)
file(REAL_PATH "${TRICK_ICG_CLANG_EXECUTABLE}" icg_clang_real)
get_filename_component(icg_clang_dir "${icg_clang_real}" DIRECTORY)
if(NOT icg_clang_dir STREQUAL llvm_tools_dir)
    message(FATAL_ERROR "TRICK_ICG_CLANG_EXECUTABLE must belong to the selected LLVM tools directory: ${LLVM_TOOLS_BINARY_DIR}")
endif()
execute_process(COMMAND "${TRICK_ICG_CLANG_EXECUTABLE}" --version
    OUTPUT_VARIABLE clang_version RESULT_VARIABLE result ERROR_VARIABLE error)
if(NOT result EQUAL 0 OR NOT clang_version MATCHES "clang version ${LLVM_VERSION_MAJOR}\\.")
    message(FATAL_ERROR "Selected Clang tool does not match LLVM ${LLVM_PACKAGE_VERSION}: ${TRICK_ICG_CLANG_EXECUTABLE}\n${clang_version}${error}")
endif()
execute_process(COMMAND "${TRICK_ICG_CLANG_EXECUTABLE}" -print-resource-dir
    OUTPUT_VARIABLE TRICK_ICG_RESOURCE_DIR OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE result ERROR_VARIABLE error)
if(NOT result EQUAL 0 OR NOT EXISTS "${TRICK_ICG_RESOURCE_DIR}/include/stddef.h")
    message(FATAL_ERROR "Clang resource headers are missing: ${TRICK_ICG_RESOURCE_DIR}. Install matching Clang builtin headers. ${error}")
endif()
# No trick-gte/config_*.mk is needed for this build-tree developer executable.
# libc++ wraps C headers: its directories must precede Clang resources.
# Replace host-Clang builtins with this LLVM's builtins, avoiding include_next
# traversing two different Clang resource versions. Resolve SDK symlinks so
# ICG's existing system-directory classification sees the same canonical paths.
set(icg_cxx_includes)
set(icg_other_includes)
foreach(path IN LISTS CMAKE_CXX_IMPLICIT_INCLUDE_DIRECTORIES)
    file(REAL_PATH "${path}" path)
    if(path MATCHES "/c[+][+](/|$)")
        list(APPEND icg_cxx_includes "${path}")
    elseif(NOT path MATCHES "/lib/clang/[^/]+/include$")
        list(APPEND icg_other_includes "${path}")
    endif()
endforeach()
file(REAL_PATH "${TRICK_ICG_RESOURCE_DIR}/include" icg_resource_include)
set(icg_system_includes ${icg_cxx_includes} "${icg_resource_include}" ${icg_other_includes})
list(REMOVE_DUPLICATES icg_system_includes)
set(TRICK_ICG_SYSTEM_INCLUDES "")
foreach(path IN LISTS icg_system_includes)
    string(REPLACE "\\" "\\\\" path "${path}")
    string(REPLACE "\"" "\\\"" path "${path}")
    string(APPEND TRICK_ICG_SYSTEM_INCLUDES "    \"${path}\",\n")
endforeach()
set(icg_source_dir "${PROJECT_SOURCE_DIR}")
string(REPLACE "\\" "\\\\" icg_source_dir "${icg_source_dir}")
string(REPLACE "\"" "\\\"" icg_source_dir "${icg_source_dir}")
configure_file(TrickICGConfig.hh.in TrickICGConfig.hh @ONLY)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/ICGConfiguration.txt"
    "LLVM: ${LLVM_PACKAGE_VERSION}\nClang tool: ${TRICK_ICG_CLANG_EXECUTABLE}\nResource directory: ${TRICK_ICG_RESOURCE_DIR}\nModel system includes: ${icg_system_includes}\nRTTI: ${LLVM_ENABLE_RTTI}\n")

if(BUILD_TESTING)
    add_test(NAME icg.smoke COMMAND "${CMAKE_COMMAND}"
        "-DICG=$<TARGET_FILE:trick-ICG>"
        "-DTEST_ROOT=${CMAKE_CURRENT_BINARY_DIR}/smoke"
        "-DTRICK_SOURCE=${PROJECT_SOURCE_DIR}"
        "-DTRICK_VERSION=${TRICK_VERSION}"
        -P "${PROJECT_SOURCE_DIR}/cmake/tests/ICG.cmake")
    set_tests_properties(icg.smoke PROPERTIES LABELS icg TIMEOUT 120)
endif()

if(BUILD_TESTING)
    add_test(NAME icg.outputs COMMAND "${CMAKE_COMMAND}"
        "-DICG=$<TARGET_FILE:trick-ICG>"
        "-DTEST_ROOT=${CMAKE_CURRENT_BINARY_DIR}/output-contract"
        "-DSYSTEM_INCLUDES=${icg_system_includes}"
        -P "${PROJECT_SOURCE_DIR}/cmake/tests/ICGOutputs.cmake")
    set_tests_properties(icg.outputs PROPERTIES LABELS icg TIMEOUT 120)
endif()
