/* PURPOSE: (Fixed array metadata conformance.) */
#ifndef ICG_ARRAYS_HH
#define ICG_ARRAYS_HH

struct ArrayModel
{
        int lead;
        int vector[3];              /* trick_units(1) vector */
        double matrix[2][3];        /* trick_units(m) positions */
        unsigned int cube[2][1][4]; /* trick_io(*o) trick_units(--) counts */
        int rank8[1][2][1][2][1][2][1][2];
};

namespace icg_array
{
    using Count = unsigned int;
    using Row   = double[3];
    struct Aliases
    {
            Count count;
            Count counts[2];
            Row rows[2]; /* trick_units(r) angles */
            double tail;
    };
}

#endif
