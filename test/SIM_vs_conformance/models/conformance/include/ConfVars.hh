/*
    PURPOSE: (Fixed variables that the variable server conformance suite reads.
              Every value is constant after default_data, so the reply bytes
              are the same on every run.)
    LIBRARY_DEPENDENCIES: (
      (conformance/src/ConfVars.cpp)
    )
*/

#ifndef CONFVARS_HH
#define CONFVARS_HH

#include <cstdio>
#include <deque>
#include <string>
#include <vector>

enum ConfColor
{
    CONF_RED   = 0,
    CONF_GREEN = 1,
    CONF_BLUE  = 2
};

enum class ConfScoped : short
{
    ALPHA = -2,
    BETA  = 7
};

class ConfInner
{
    public:
        int a;       /* -- inner integer */
        double b[2]; /* m inner array */
};

class ConfLabel
{
    public:
        char text[16]; /* -- label text */
};

class ConfBits
{
    public:
        unsigned int u3 : 3; /* -- unsigned 3-bit field */
        unsigned int u5 : 5; /* -- unsigned 5-bit field */
        int s4 : 4;          /* -- signed 4-bit field */
        int s12 : 12;        /* -- signed 12-bit field */
};

class ConfVars
{
    public:
        ConfVars();
        int default_vars();
        int init();
        int shutdown();

        /* Append `count` elements to vec, so it moves its elements, then set vec[0] to `first`.
           For test_stl_element_after_the_vector_moves. */
        void grow_vec(int count, double first);

        /* Scalars, one per TRICK_TYPE */
        char c;                 /* -- char */
        signed char sc;         /* -- signed char */
        unsigned char uc;       /* -- unsigned char */
        short s;                /* -- short */
        unsigned short us;      /* -- unsigned short */
        int i32;                /* -- int */
        unsigned int u32;       /* -- unsigned int */
        long l;                 /* -- long */
        unsigned long ul;       /* -- unsigned long */
        long long ll;           /* -- long long */
        unsigned long long ull; /* -- unsigned long long */
        float f;                /* -- float */
        double d;               /* -- double */
        bool b_true;            /* -- bool, true */
        bool b_false;           /* -- bool, false */
        wchar_t wc;             /* -- wide char */
        ConfColor color;        /* -- unscoped enum */
        ConfScoped scoped;      /* -- scoped enum with short base */

        /* Floating-point edge values */
        double d_neg;   /* -- negative double */
        double d_tiny;  /* -- small double */
        double d_huge;  /* -- large double */
        double d_third; /* -- needs 16 digits */
        double d_inf;   /* -- +inf */
        double d_nan;   /* -- quiet NaN */
        float f_third;  /* -- needs 8 digits */

        /* Integer limits */
        int i32_min;                /* -- INT_MIN */
        unsigned long long ull_max; /* -- ULLONG_MAX */

        /* Strings */
        char carr[16];         /* -- char array, NUL inside */
        char carr_full[8];     /* -- char array with no NUL */
        char* cptr;            /* -- C string */
        char* cptr_null;       /* -- NULL C string */
        char* cptr_escape;     /* -- C string with control characters */
        std::string str;       /* -- std::string */
        std::string str_empty; /* -- empty std::string */
        wchar_t warr[8];       /* -- wide char array */
        wchar_t* wptr;         /* -- wide C string */

        /* Arrays */
        int iarr[5];            /* -- 1-D int array */
        double darr[3][2];      /* m 2-D double array */
        unsigned char ucarr[4]; /* -- unsigned char array */
        bool barr[3];           /* -- bool array */
        double big[2000];       /* -- larger than one 8192-byte packet */

        /* Pointers */
        double* dptr;         /* m pointer to 4 doubles */
        int* iptr_null;       /* -- NULL pointer */
        ConfInner* inner_ptr; /* -- pointer to a class */
        void* vptr;           /* -- void pointer */
        FILE* fp;             /* -- FILE pointer */

        /* Units */
        double pos;      /* m position */
        double ang;      /* rad angle */
        double speed;    /* m/s speed */
        double temp;     /* degC temperature */
        int count_m;     /* m integer with units */
        double unitless; /* -- unitless */
        double ratio;    /* 1 dimensionless */

        /* Structured */
        ConfInner inner; /* -- nested class */
        ConfBits bits;   /* -- bitfields */

        /* STL */
        std::vector<double> vec;    /* -- vector of double */
        std::vector<int> vec_empty; /* -- empty vector */
        std::deque<int> deq;        /* -- deque of int */
        std::vector<ConfLabel*> label_ptrs; /* -- vector of pointers to a class with a char array */

        /* Permissions */
        int read_only;            /**< -- trick_io(*o) not settable */
        int settable;             /* -- settable */
        double settable_d;        /* m settable double */
        std::string settable_str; /* -- settable string */

        /* Long string, larger than the 4096-byte stage buffer */
        std::string str_long; /* -- 5000 characters */

        /* The suite reads this to find the end of each reply. */
        char end_marker[32]; /* -- end-of-case marker */
};

#endif
