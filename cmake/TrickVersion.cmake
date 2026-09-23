# Keep prerelease text outside project(VERSION), using trick-version's authority.
function(trick_read_version version_file)
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${version_file}")
    file(READ "${version_file}" version_text)
    string(STRIP "${version_text}" version_text)
    if(NOT version_text MATCHES
        "^current_version[ \t]*=[ \t]*\"([0-9]+\\.[0-9]+\\.[0-9]+([-+][0-9A-Za-z.+-]+)?)\"$")
        message(FATAL_ERROR
            "Invalid Trick version in ${version_file}: expected "
            "current_version = \"major.minor.patch[-suffix]\".")
    endif()
    set(full_version "${CMAKE_MATCH_1}")
    string(REGEX MATCH "^[0-9]+\\.[0-9]+\\.[0-9]+" numeric_version "${full_version}")
    set(TRICK_VERSION "${full_version}" PARENT_SCOPE)
    set(TRICK_VERSION_NUMBER "${numeric_version}" PARENT_SCOPE)
endfunction()
