# These tools run on the host; they are not runtime link dependencies.
find_package(BISON REQUIRED)
find_package(FLEX REQUIRED)
find_package(Perl 5.14 REQUIRED)
execute_process(COMMAND "${PERL_EXECUTABLE}" -MText::Balanced -MDigest::MD5 -e "exit 0"
    RESULT_VARIABLE perl_modules OUTPUT_VARIABLE perl_output ERROR_VARIABLE perl_error)
if(NOT perl_modules STREQUAL "0")
    message(FATAL_ERROR "Selected Perl lacks Text::Balanced or Digest::MD5: ${PERL_EXECUTABLE}\n${perl_error}")
endif()

include("${CMAKE_CURRENT_LIST_DIR}/TrickPython.cmake")
include("${CMAKE_CURRENT_LIST_DIR}/TrickSWIG.cmake")
list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/modules")
find_package(UDUNITS2 REQUIRED)
