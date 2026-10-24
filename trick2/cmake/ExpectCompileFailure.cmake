# Each CTest invocation has its own output, so parallel tests do not race.
separate_arguments(_driver_args NATIVE_COMMAND "${CXX_COMPILER_ARG1}")
separate_arguments(_flags NATIVE_COMMAND "${CXX_FLAGS}")
execute_process(
    COMMAND "${CXX_COMPILER}" ${_driver_args} ${_flags}
        -std=c++26 ${REFLECTION_OPTIONS} "-I${SOURCE_DIR}/include"
        -c "${SOURCE_DIR}/tests/reflection_invalid_${CASE}.cpp"
        -o "${BINARY_DIR}/reflection_invalid_${CASE}.o"
    RESULT_VARIABLE _result OUTPUT_VARIABLE _stdout ERROR_VARIABLE _stderr)
if(_result EQUAL 0)
    message(FATAL_ERROR "Invalid schema '${CASE}' unexpectedly compiled")
endif()
string(FIND "${_stdout}\n${_stderr}" "${EXPECTED}" _match)
if(_match LESS 0)
    message(FATAL_ERROR
        "Schema '${CASE}' failed for the wrong reason. Expected '${EXPECTED}'.\n${_stdout}\n${_stderr}")
endif()
