/*
PURPOSE: (Write one staged value as ASCII text, as the old server did.)

The text of each value is what the old VariableReference::writeValueAscii
wrote, with these changes on purpose (see the rewrite plan, Phase 0 and
Phase 2 findings):

  * An enum is read with its real size, not always as a 4-byte int.
  * Text stops at a NUL or at the staged count, never past the value.
  * A narrow byte of 0x80 or more is written as \xNN. The old server wrote
    \xffffffNN, because it passed a signed char to "%02x".
  * Wide text is escaped by the C locale's rules, whatever locale the
    simulation set.
  * An integer that a units conversion puts out of range is clamped to the
    type's range. The old cast was undefined behavior.

Numbers are formatted in the C locale: %.16g for double, %.8g for float.
*/

#ifndef TRICK_VS_ASCIIENCODER_HH
#define TRICK_VS_ASCIIENCODER_HH

#include "trick/vs/FieldDesc.hh"
#include "trick/vs/Interfaces.hh"

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>

namespace Trick
{
    namespace vs
    {

        /**
         * Append the text of one value to `out`: the elements separated by ','
         * (or the text of a string), then " {units}" if `units` is not empty, or
         * " {--}" if the variable's units are "--".
         *
         * `conversion` (may be null) applies to the numeric types the old server
         * converted: char, short, int, long, long long, their unsigned forms,
         * float, double, bool and enum. A null conversion prints the value
         * exactly.
         *
         * `data` holds desc.byte_size() bytes.
         */
        void append_ascii_value(std::string& out, const FieldDesc& desc, const unsigned char* data,
                                const Conversion* conversion, std::string_view units);

        /**
         * Append narrow text: printable ASCII as it is; \n \t \b \a \f \v as
         * escapes; '\r' as "\n" (as the old server did); any other byte as \xNN.
         * Stops at the first NUL or after `size` bytes.
         */
        void append_escaped_narrow(std::string& out, const unsigned char* data, std::size_t size);

        /**
         * Append wide text, as the old wcs_to_ncs() did in the C locale: printable
         * ASCII as it is, except that ' " ? and \ get a backslash; control
         * characters as \a \b \f \n \t \v ('\r' as \n); other values up to 0xFF
         * as \xNN, up to 0xFFFF as \uNNNN, and above as \UNNNNNNNN. Stops at the
         * first NUL or after `count` elements of `element_size` (2 or 4) bytes.
         */
        void append_escaped_wide(std::string& out, const unsigned char* data, std::size_t count,
                                 uint32_t element_size);

    } // namespace vs
} // namespace Trick

#endif
