/* PURPOSE: (UTF-16 code-unit metadata conformance.) */
#ifndef ICG_BASELINE_UTF16_HH
#define ICG_BASELINE_UTF16_HH

struct Utf16Model
{
    char16_t code; /* trick_units(1) code unit */
    char16_t text[6]; /* trick_units(1) code units */
    char16_t grid[2][3];
    char16_t maximum;
};

namespace icg_utf16
{
    using Code = char16_t;
    using Text = Code[4];
    struct Aliases
    {
        Code code;
        Text text;
        Code tail;
    };
}

#endif
