/* PURPOSE: (Builtin scalar metadata conformance.) */
#ifndef ICG_BASELINE_SCALARS_HH
#define ICG_BASELINE_SCALARS_HH

// Independent legacy/native scalar coverage, including padding around arrays.
struct ScalarModel
{
        bool enabled;     /* trick_units(1) enabled */
        char code;        /* trick_units(1) code */
        float gain;       /* trick_units(m) gain */
        long counter;     /* trick_units(1) counter */
        bool flags[2][3]; /* trick_units(1) flags */
        float samples[3]; /* trick_units(m) samples */
        char label[8];    /* trick_units(1) label */
        long limits[2];   /* trick_units(1) limits */
};

namespace icg_scalar
{
    using Flag = bool;
    typedef float Gain;
    using Code   = char;
    using Count  = long;
    using Counts = Count[2];

    struct Aliases
    {
            Flag flag;
            Code code;
            Gain gain;
            Count counter;
            Counts counts;
    };
}

#endif
