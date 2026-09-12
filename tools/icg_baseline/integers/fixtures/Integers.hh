/* PURPOSE: (Integer width and signedness metadata conformance.) */
#ifndef ICG_BASELINE_INTEGERS_HH
#define ICG_BASELINE_INTEGERS_HH

struct IntegerModel
{
        signed char signed_code;       /* trick_units(1) signed code */
        unsigned char byte;            /* trick_units(1) byte */
        short small;                   /* trick_units(m) small */
        unsigned short small_count;    /* trick_units(1) small count */
        unsigned long count;           /* trick_units(1) count */
        long long wide;                /* trick_units(m) wide */
        unsigned long long wide_count; /* trick_units(1) wide count */
        signed char signed_codes[2];
        unsigned char bytes[3];
        short smalls[2][3];
        unsigned short small_counts[2];
        unsigned long counts[2];
        long long wides[2];
        unsigned long long wide_counts[2];
};

namespace icg_integer
{
    using SignedCode = signed char;
    using Byte       = unsigned char;
    typedef short Small;
    using SmallCount = unsigned short;
    using Count      = unsigned long;
    using Wide       = long long;
    using WideCount  = unsigned long long;
    using WideCounts = WideCount[2];

    struct Aliases
    {
            SignedCode signed_code;
            Byte byte;
            Small small;
            SmallCount small_count;
            Count count;
            Wide wide;
            WideCount wide_count;
            WideCounts wide_counts;
    };
}

#endif
