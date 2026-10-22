#include "conformance/include/ConfVars.hh"

#include "trick/memorymanager_c_intf.h"

#include <climits>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <limits>

ConfVars::ConfVars()
{
    std::memset(carr, 0, sizeof(carr));
    std::memset(carr_full, 0, sizeof(carr_full));
    std::memset(warr, 0, sizeof(warr));
    cptr        = nullptr;
    cptr_null   = nullptr;
    cptr_escape = nullptr;
    wptr        = nullptr;
    dptr        = nullptr;
    iptr_null   = nullptr;
    inner_ptr   = nullptr;
    vptr        = nullptr;
    fp          = nullptr;
}

int ConfVars::default_vars()
{
    c       = 'A';
    sc      = -5;
    uc      = 200;
    s       = -1234;
    us      = 54321;
    i32     = -123456789;
    u32     = 4000000000u;
    l       = -1234567890123L;
    ul      = 9876543210UL;
    ll      = -9000000000000000000LL;
    ull     = 18000000000000000000ULL;
    f       = 1.5f;
    d       = 3.141592653589793;
    b_true  = true;
    b_false = false;
    wc      = L'W';
    color   = CONF_BLUE;
    scoped  = ConfScoped::ALPHA;

    d_neg   = -2.5;
    d_tiny  = 1.0e-300;
    d_huge  = 1.0e+300;
    d_third = 1.0 / 3.0;
    d_inf   = std::numeric_limits<double>::infinity();
    d_nan   = std::numeric_limits<double>::quiet_NaN();
    f_third = 1.0f / 3.0f;

    i32_min = INT_MIN;
    ull_max = ULLONG_MAX;

    std::strcpy(carr, "hello");
    std::memcpy(carr_full, "ABCDEFGH", sizeof(carr_full));
    str       = "std string value";
    str_empty = "";
    std::wcscpy(warr, L"wide");

    for (int k = 0; k < 5; k++)
    {
        iarr[k] = (k + 1) * 10;
    }
    for (int r = 0; r < 3; r++)
    {
        for (int k = 0; k < 2; k++)
        {
            darr[r][k] = r + k * 0.5;
        }
    }
    ucarr[0] = 0;
    ucarr[1] = 1;
    ucarr[2] = 127;
    ucarr[3] = 255;
    barr[0]  = true;
    barr[1]  = false;
    barr[2]  = true;
    for (int k = 0; k < 2000; k++)
    {
        big[k] = k + 0.25;
    }

    pos      = 1000.0;
    ang      = 3.141592653589793;
    speed    = 10.0;
    temp     = 100.0;
    count_m  = 3;
    unitless = 42.0;
    ratio    = 0.5;

    inner.a    = 7;
    inner.b[0] = 1.25;
    inner.b[1] = -1.25;

    bits.u3  = 5;
    bits.u5  = 31;
    bits.s4  = -3;
    bits.s12 = 1000;

    vec = { 1.5, 2.5, 3.5 };
    vec_empty.clear();
    deq = { 4, 5, 6, 7 };

    read_only    = 11;
    settable     = 12;
    settable_d   = 2.0;
    settable_str = "before";

    str_long.assign(5000, 'x');

    std::memset(end_marker, 0, sizeof(end_marker));
    std::strcpy(end_marker, "@@vs-conformance-end@@");

    return 0;
}

int ConfVars::init()
{
    /* Memory that the Memory Manager tracks, so pointer paths resolve. */
    cptr        = (char*)TMM_strdup((char*)"c string");
    cptr_escape = (char*)TMM_strdup((char*)"tab\there\nnew \"q\" \\ end");
    wptr        = (wchar_t*)TMM_declare_var_1d("wchar_t", 6);
    std::wcscpy(wptr, L"wptr!");
    dptr = (double*)TMM_declare_var_1d("double", 4);
    for (int k = 0; k < 4; k++)
    {
        dptr[k] = 0.5 * (k + 1);
    }
    inner_ptr       = (ConfInner*)TMM_declare_var_1d("ConfInner", 1);
    inner_ptr->a    = 99;
    inner_ptr->b[0] = 9.5;
    inner_ptr->b[1] = -9.5;
    for (int k = 0; k < 2; k++)
    {
        ConfLabel* label = (ConfLabel*)TMM_declare_var_1d("ConfLabel", 1);
        std::snprintf(label->text, sizeof(label->text), "label %d", k);
        label_ptrs.push_back(label);
    }
    return 0;
}

int ConfVars::shutdown() { return 0; }
