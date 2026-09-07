#pragma once

struct CxxRecord
{
        int value;
};

int cxx_function(int value = 1);

extern "C++"
{
    int explicit_cxx_function(int value);
}

extern "C"
{
    typedef struct
    {
            int day;
            double seconds;
    } CTime;

    int c_function(CTime* value);
}

namespace linkage_fixture
{
    extern "C" int namespaced_c_function(int value);
    int namespaced_cxx_function(int value);
}
