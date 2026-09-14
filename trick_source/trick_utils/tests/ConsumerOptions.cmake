cmake_minimum_required(VERSION 3.26)

file(READ "${OPTIONS_FILE}" options)
string(STRIP "${options}" options)
if("-Wall" IN_LIST options OR "-Wextra" IN_LIST options)
    message(FATAL_ERROR "Trick's private warnings leaked into the consumer: ${options}")
endif()
