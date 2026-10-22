#include "trick/vs/FieldDesc.hh"

#include <cstdint>
#include <limits>

namespace Trick
{
    namespace vs
    {

        FieldDesc FieldDesc::bad_ref() noexcept { return scalar(WireType::BadRef, 4); }

        FieldDesc FieldDesc::scalar(WireType type, uint32_t size) noexcept { return array(type, size, 1); }

        FieldDesc FieldDesc::array(WireType type, uint32_t element_size, uint32_t count) noexcept
        {
            FieldDesc d;
            d.type         = type;
            d.element_size = element_size;
            d.count        = count;
            return d;
        }

        FieldDesc FieldDesc::narrow_string(uint32_t length) noexcept
        {
            FieldDesc d = array(WireType::String, 1, length + 1);
            d.text      = Text::Narrow;
            return d;
        }

        FieldDesc FieldDesc::wide_string(uint32_t length) noexcept
        {
            FieldDesc d = array(WireType::WideString, sizeof(wchar_t), length + 1);
            d.text      = Text::Wide;
            return d;
        }

        FieldDesc FieldDesc::char_array(uint32_t size) noexcept
        {
            FieldDesc d = array(WireType::Character, 1, size);
            d.text      = Text::Narrow;
            return d;
        }

        bool operator==(const FieldDesc& a, const FieldDesc& b) noexcept
        {
            return a.type == b.type && a.element_size == b.element_size && a.count == b.count && a.text == b.text
                && a.bitfield.start == b.bitfield.start && a.bitfield.width == b.bitfield.width
                && a.units_dashdash == b.units_dashdash;
        }

        bool operator!=(const FieldDesc& a, const FieldDesc& b) noexcept { return !(a == b); }

        namespace
        {

            bool one_of(uint32_t size, uint32_t a, uint32_t b = 0, uint32_t c = 0, uint32_t d = 0) noexcept
            {
                return size == a || (b != 0 && size == b) || (c != 0 && size == c) || (d != 0 && size == d);
            }

        } // namespace

        const char* validate(const FieldDesc& desc) noexcept
        {
            const uint32_t s = desc.element_size;
            if (static_cast<uint64_t>(s) * desc.count > std::numeric_limits<uint32_t>::max())
            {
                return "value is larger than 4 GiB";
            }

            switch (desc.type)
            {
            case WireType::BadRef:
                if (s != 4 || desc.count != 1)
                {
                    return "BAD_REF must be one 4-byte value";
                }
                break;
            case WireType::Character:
            case WireType::UnsignedCharacter:
            case WireType::String:
            case WireType::Boolean:
                if (s != 1)
                {
                    return "element size must be 1";
                }
                break;
            case WireType::Short:
            case WireType::UnsignedShort:
                if (s != 2)
                {
                    return "element size must be 2";
                }
                break;
            case WireType::Integer:
            case WireType::UnsignedInteger:
            case WireType::Float:
                if (s != 4)
                {
                    return "element size must be 4";
                }
                break;
            case WireType::Double:
            case WireType::LongLong:
            case WireType::UnsignedLongLong:
                if (s != 8)
                {
                    return "element size must be 8";
                }
                break;
            case WireType::Long:
            case WireType::UnsignedLong:
                if (!one_of(s, 4, 8))
                {
                    return "element size must be 4 or 8";
                }
                break;
            case WireType::WideCharacter:
            case WireType::WideString:
                if (!one_of(s, 2, 4))
                {
                    return "element size must be 2 or 4";
                }
                break;
            case WireType::Enumerated:
                if (!one_of(s, 1, 2, 4, 8))
                {
                    return "enum size must be 1, 2, 4 or 8";
                }
                break;
            case WireType::Bitfield:
            case WireType::UnsignedBitfield:
                if (!one_of(s, 1, 2, 4, 8))
                {
                    return "bitfield storage must be 1, 2, 4 or 8 bytes";
                }
                if (desc.bitfield.width == 0 || desc.bitfield.start + desc.bitfield.width > s * 8)
                {
                    return "bitfield does not fit in its storage";
                }
                if (desc.count != 1)
                {
                    return "a bitfield is one value";
                }
                break;
            case WireType::Void:
            case WireType::FilePtr:
            case WireType::VoidPtr:
            case WireType::Structured:
            case WireType::Opaque:
            case WireType::Stl:
                // Sent as raw bytes in binary and as an empty field in ASCII.
                break;
            default:
                return "unknown wire type";
            }

            if (desc.text == Text::Narrow && s != 1)
            {
                return "narrow text must have 1-byte elements";
            }
            if (desc.text == Text::Wide && desc.type != WireType::WideCharacter && desc.type != WireType::WideString)
            {
                return "wide text must be wchar_t";
            }
            if (desc.is_bitfield() != (desc.bitfield.width != 0))
            {
                return "bitfield position given for a value that is not a bitfield";
            }
            return nullptr;
        }

    } // namespace vs
} // namespace Trick
