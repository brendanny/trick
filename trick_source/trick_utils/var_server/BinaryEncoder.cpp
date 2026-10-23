#include "trick/vs/BinaryEncoder.hh"

#include <cstring>
#include <limits>

namespace Trick
{
    namespace vs
    {

        namespace
        {

            template <class T> T load(const unsigned char* p) noexcept
            {
                T v;
                std::memcpy(&v, p, sizeof v);
                return v;
            }

            constexpr bool little_endian() noexcept
            {
#if defined(__BYTE_ORDER__) && defined(__ORDER_BIG_ENDIAN__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
                return false;
#else
                return true;
#endif
            }

            void append_swapped(std::string& out, const unsigned char* p, std::size_t n)
            {
                for (std::size_t k = n; k > 0; --k)
                    out += static_cast<char>(p[k - 1]);
            }

        } // namespace

        int64_t extract_bitfield(const unsigned char* storage, uint32_t storage_size, Bitfield bf,
                                 bool is_signed) noexcept
        {
            const unsigned bits = bf.width;
            if (bits == 0)
                return 0;
            const unsigned unit_bits = storage_size * 8;
            uint64_t v;
            switch (storage_size)
            {
                case 1:
                    v = load<uint8_t>(storage);
                    break;
                case 2:
                    v = load<uint16_t>(storage);
                    break;
                case 4:
                    v = load<uint32_t>(storage);
                    break;
                default:
                    v = load<uint64_t>(storage);
                    break;
            }
            if (bits >= unit_bits || bf.start + bits > unit_bits)
            {
                // Not a valid position (validate() rejects it); give the whole unit.
            }
            else if (little_endian())
            {
                // ICG counts start from the most significant bit.
                v >>= (unit_bits - bf.start - bits);
            }
            else
            {
                v >>= bf.start;
            }
            const uint64_t mask = bits >= 64 ? ~uint64_t(0) : ((uint64_t(1) << bits) - 1);
            v &= mask;
            if (is_signed && bits < 64 && (v & (uint64_t(1) << (bits - 1))) != 0)
                v |= ~mask; // sign-extend
            return static_cast<int64_t>(v);
        }

        std::size_t binary_var_size(std::string_view name, const FieldDesc& desc, bool nonames) noexcept
        {
            return (nonames ? 0 : 4 + name.size()) + 8 + desc.byte_size();
        }

        void append_int32(std::string& out, int32_t value, bool byteswap)
        {
            unsigned char b[4];
            std::memcpy(b, &value, 4);
            if (byteswap)
                append_swapped(out, b, 4);
            else
                out.append(reinterpret_cast<const char*>(b), 4);
        }

        void append_binary_value(std::string& out, const FieldDesc& desc, const unsigned char* data, bool byteswap)
        {
            const uint32_t size = desc.element_size;
            if (desc.is_bitfield())
            {
                // The old server sent the extracted value, as many bytes as the
                // storage unit, from an int (low bytes first on little-endian).
                const int64_t v = extract_bitfield(data, size, desc.bitfield, desc.type == WireType::Bitfield);
                unsigned char b[8];
                if (size == 8)
                {
                    std::memcpy(b, &v, 8);
                }
                else
                {
                    const int32_t i = static_cast<int32_t>(v);
                    std::memcpy(b, &i, 4);
                    if (!little_endian())
                        std::memmove(b, b + (4 - size), size);
                }
                // Phase 2 fix: the old server never swapped a bitfield.
                if (byteswap)
                    append_swapped(out, b, size);
                else
                    out.append(reinterpret_cast<const char*>(b), size);
                return;
            }

            const std::size_t total = desc.byte_size();
            if (!byteswap || size == 1)
            {
                out.append(reinterpret_cast<const char*>(data), total);
                return;
            }
            if (size != 2 && size != 4 && size != 8)
            {
                // As the old server: values of other element sizes are sent as zeros.
                out.append(total, '\0');
                return;
            }
            for (uint32_t i = 0; i < desc.count; ++i)
                append_swapped(out, data + static_cast<std::size_t>(i) * size, size);
        }

        void append_binary_var(std::string& out, std::string_view name, const FieldDesc& desc,
                               const unsigned char* data, bool nonames, bool byteswap)
        {
            if (!nonames)
            {
                append_int32(out, static_cast<int32_t>(name.size()), byteswap);
                out.append(name.data(), name.size());
            }
            append_int32(out, static_cast<int32_t>(desc.type), byteswap);
            append_int32(out, static_cast<int32_t>(desc.byte_size()), byteswap);
            append_binary_value(out, desc, data, byteswap);
        }

    } // namespace vs
} // namespace Trick
