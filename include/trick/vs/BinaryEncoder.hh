/*
PURPOSE: (Write one staged value in the binary format, as the old server did.)

One variable is written as

    [name length (int32)] [name] type (int32) size (int32) value

The name length and the name are left out in "nonames" mode. Numbers are in
host byte order, or swapped when the client asked for byteswap. Binary
values are always in the variable's own units.

Changes on purpose (rewrite plan, Phase 0 and Phase 2 findings): byteswap
swaps each staged element by its element size, so strings, pointer
elements, indexed elements and bitfields are swapped correctly. The old
server swapped as many elements as the declared array had, which zeroed
strings and pointer elements, wrote past one indexed element, and never
swapped a bitfield.
*/

#ifndef TRICK_VS_BINARYENCODER_HH
#define TRICK_VS_BINARYENCODER_HH

#include "trick/vs/FieldDesc.hh"

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>

namespace Trick
{
    namespace vs
    {

        /**
         * The value of a bitfield, as Trick's GET_BITFIELD read it. `storage`
         * holds `storage_size` (1, 2, 4 or 8) bytes; bf.start counts from the
         * most significant bit on a little-endian host and from the least
         * significant bit on a big-endian host, as ICG writes it. A signed
         * bitfield is sign-extended.
         */
        int64_t extract_bitfield(const unsigned char* storage, uint32_t storage_size, Bitfield bf,
                                 bool is_signed) noexcept;

        /** Bytes that one variable takes in a binary message. */
        std::size_t binary_var_size(std::string_view name, const FieldDesc& desc, bool nonames) noexcept;

        /** Append an int32 in host order, or swapped. */
        void append_int32(std::string& out, int32_t value, bool byteswap);

        /** Append only the value bytes of a variable. */
        void append_binary_value(std::string& out, const FieldDesc& desc, const unsigned char* data, bool byteswap);

        /** Append one whole variable: name (unless `nonames`), type, size and value. */
        void append_binary_var(std::string& out, std::string_view name, const FieldDesc& desc,
                               const unsigned char* data, bool nonames, bool byteswap);

    } // namespace vs
} // namespace Trick

#endif
