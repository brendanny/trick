/*
PURPOSE: (Describe one staged value: its wire type, element size and count.)

The adapter fills a FieldDesc from the Memory Manager's ATTRIBUTES. The
encoders read only the FieldDesc, so the core library never sees
ATTRIBUTES.
*/

#ifndef TRICK_VS_FIELDDESC_HH
#define TRICK_VS_FIELDDESC_HH

#include "trick/vs/WireTypes.hh"

#include <cstddef>
#include <cstdint>

namespace Trick
{
    namespace vs
    {

        /** How the ASCII encoder prints a value. */
        enum class Text : uint8_t
        {
            None,   ///< print each element as a number, comma-separated
            Narrow, ///< print the bytes as an escaped string (char[], char*, std::string)
            Wide    ///< print wchar_t elements as a narrowed, escaped string
        };

        /** Position of a bitfield in its storage unit. */
        struct Bitfield
        {
                uint16_t start = 0; ///< first bit, as Trick's ATTRIBUTES index[0].start
                uint16_t width = 0; ///< number of bits; 0 if the value is not a bitfield
        };

        /**
         * One staged value.
         *
         * element_size is the real size of one element. An enum with a short base
         * type has element_size 2, not 4 (Phase 0 fix: the old ASCII writer read 4
         * bytes for every enum).
         *
         * count is the number of elements that were staged. For a char array, a
         * string or an indexed element it is what the snapshot holds, never the
         * declared array length (Phase 0 fixes: strlen past a char array with no
         * NUL; byteswap past one indexed element).
         */
        struct FieldDesc
        {
                WireType type         = WireType::BadRef;
                uint32_t element_size = 0;
                uint32_t count        = 0;
                Text text             = Text::None;
                Bitfield bitfield;
                /// The variable's units are "--": print " {--}" when units are requested.
                bool units_dashdash = false;

                /** Bytes the value takes in a snapshot: element_size * count. */
                std::size_t byte_size() const noexcept { return static_cast<std::size_t>(element_size) * count; }

                bool is_bad_ref() const noexcept { return type == WireType::BadRef; }

                bool is_bitfield() const noexcept
                {
                    return type == WireType::Bitfield || type == WireType::UnsignedBitfield;
                }

                /** The description of a name that does not resolve: type 25, 4 bytes, value 0. */
                static FieldDesc bad_ref() noexcept;

                /** A scalar of the given type and size. */
                static FieldDesc scalar(WireType type, uint32_t size) noexcept;

                /** An array of `count` elements. */
                static FieldDesc array(WireType type, uint32_t element_size, uint32_t count) noexcept;

                /** A narrow string of `length` bytes plus its NUL (binary type 3). */
                static FieldDesc narrow_string(uint32_t length) noexcept;

                /** A wide string of `length` wchar_t plus its NUL (binary type 19). */
                static FieldDesc wide_string(uint32_t length) noexcept;

                /** A char array of `size` bytes (binary type 1), printed as text in ASCII. */
                static FieldDesc char_array(uint32_t size) noexcept;
        };

        bool operator==(const FieldDesc& a, const FieldDesc& b) noexcept;
        bool operator!=(const FieldDesc& a, const FieldDesc& b) noexcept;

        /**
         * Check a FieldDesc for values the encoders cannot handle. Returns nullptr
         * if it is valid, or a reason. Each element size must be one a type allows:
         * an Enumerated value may be 1, 2, 4 or 8 bytes; a Double must be 8.
         */
        const char* validate(const FieldDesc& desc) noexcept;

    } // namespace vs
} // namespace Trick

#endif
