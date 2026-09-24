cmake_minimum_required(VERSION 3.26)
project(TrickSDKConsumer LANGUAGES CXX)
find_package(Trick CONFIG REQUIRED COMPONENTS Runtime)
add_executable(embedded main.cpp)
trick_enable_runtime(embedded)
enable_testing()
add_test(NAME embedded COMMAND "${CMAKE_COMMAND}" -E env
    "PYTHONPATH=${Trick_PYTHON_DIR}" "PYTHONDONTWRITEBYTECODE=1" "$<TARGET_FILE:embedded>")
