#include "trick/vs/AsciiEncoder.hh"

#include "trick/vs/BinaryEncoder.hh"
#include "trick/vs/CLocale.hh"

#include <charconv>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <limits>
#include <type_traits>

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

            template <class T> void append_int(std::string& out, T v)
            {
                char buf[24];
                const auto r = std::to_chars(buf, buf + sizeof buf, v);
                out.append(buf, r.ptr);
            }

            /** (T)value, clamped to T's range; NaN gives 0. The old C cast was undefined out of range. */
            template <class T> T saturate(double v) noexcept
            {
                if (std::isnan(v))
                    return 0;
                if (v <= static_cast<double>(std::numeric_limits<T>::min()))
                    return std::numeric_limits<T>::min();
                if (v >= static_cast<double>(std::numeric_limits<T>::max()))
                    return std::numeric_limits<T>::max();
                return static_cast<T>(v);
            }

            /** An integer element: through the conversion if there is one, as (T)cv_convert_double(). */
            template <class T> void append_converted_int(std::string& out, T raw, const Conversion* conversion)
            {
                if (conversion == nullptr)
                    append_int(out, raw);
                else
                    append_int(out, saturate<T>(conversion->apply(static_cast<double>(raw))));
            }

            void append_double(std::string& out, double v, int precision)
            {
                char buf[40];
                const int n = std::snprintf(buf, sizeof buf, "%.*g", precision, v);
                out.append(buf, static_cast<std::size_t>(n));
            }

            int64_t load_signed(const unsigned char* p, uint32_t size) noexcept
            {
                switch (size)
                {
                    case 1:
                        return load<int8_t>(p);
                    case 2:
                        return load<int16_t>(p);
                    case 4:
                        return load<int32_t>(p);
                    default:
                        return load<int64_t>(p);
                }
            }

            void append_element(std::string& out, const FieldDesc& desc, const unsigned char* p,
                                const Conversion* conversion)
            {
                const uint32_t size = desc.element_size;
                switch (desc.type)
                {
                    case WireType::Character:
                        // A single char prints as a number: (int)cv_convert_double(c).
                        append_converted_int<int>(out, static_cast<char>(p[0]), conversion);
                        break;
                    case WireType::UnsignedCharacter:
                        append_converted_int<unsigned int>(out, p[0], conversion);
                        break;
                    case WireType::Boolean:
                        append_converted_int<int>(out, p[0] != 0 ? 1 : 0, conversion);
                        break;
                    case WireType::Short:
                        append_converted_int<short>(out, load<short>(p), conversion);
                        break;
                    case WireType::UnsignedShort:
                        append_converted_int<unsigned short>(out, load<unsigned short>(p), conversion);
                        break;
                    case WireType::Integer:
                        append_converted_int<int>(out, load<int>(p), conversion);
                        break;
                    case WireType::UnsignedInteger:
                        append_converted_int<unsigned int>(out, load<unsigned int>(p), conversion);
                        break;
                    case WireType::Enumerated:
                        // Phase 0 fix: the real size, not always a 4-byte int.
                        if (size == 8)
                            append_converted_int<long long>(out, load<long long>(p), conversion);
                        else
                            append_converted_int<int>(out, static_cast<int>(load_signed(p, size)), conversion);
                        break;
                    case WireType::Long:
                    case WireType::LongLong:
                        if (size == 4)
                            append_converted_int<int32_t>(out, load<int32_t>(p), conversion);
                        else
                            append_converted_int<long long>(out, load<long long>(p), conversion);
                        break;
                    case WireType::UnsignedLong:
                    case WireType::UnsignedLongLong:
                        if (size == 4)
                            append_converted_int<uint32_t>(out, load<uint32_t>(p), conversion);
                        else
                            append_converted_int<unsigned long long>(out, load<unsigned long long>(p), conversion);
                        break;
                    case WireType::Float:
                    {
                        float f = load<float>(p);
                        if (conversion != nullptr)
                            f = static_cast<float>(conversion->apply(f));
                        append_double(out, f, 8);
                        break;
                    }
                    case WireType::Double:
                    {
                        double d = load<double>(p);
                        if (conversion != nullptr)
                            d = conversion->apply(d);
                        append_double(out, d, 16);
                        break;
                    }
                    case WireType::WideCharacter:
                        // A single wchar_t prints as its number, with no conversion.
                        if (size == 2)
                            append_int(out, load<uint16_t>(p));
                        else
                            append_int(out, load<int32_t>(p));
                        break;
                    case WireType::Bitfield:
                        append_int(out, extract_bitfield(p, size, desc.bitfield, true));
                        break;
                    case WireType::UnsignedBitfield:
                        append_int(out, extract_bitfield(p, size, desc.bitfield, false));
                        break;
                    case WireType::BadRef:
                        out += "BAD_REF";
                        break;
                    default:
                        // Void, String without text, FilePtr, VoidPtr, Structured, Opaque,
                        // Stl: an empty field, as in the old server.
                        break;
                }
            }

            bool needs_c_locale(WireType t) noexcept { return t == WireType::Float || t == WireType::Double; }

        } // namespace

        void append_escaped_narrow(std::string& out, const unsigned char* data, std::size_t size)
        {
            for (std::size_t i = 0; i < size && data[i] != 0; ++i)
            {
                const unsigned char c = data[i];
                if (c >= 0x20 && c <= 0x7E)
                {
                    out += static_cast<char>(c);
                    continue;
                }
                switch (c)
                {
                    case '\n':
                    case '\r':
                        out += "\\n";
                        break;
                    case '\t':
                        out += "\\t";
                        break;
                    case '\b':
                        out += "\\b";
                        break;
                    case '\a':
                        out += "\\a";
                        break;
                    case '\f':
                        out += "\\f";
                        break;
                    case '\v':
                        out += "\\v";
                        break;
                    default:
                    {
                        char buf[8];
                        std::snprintf(buf, sizeof buf, "\\x%02x", static_cast<unsigned int>(c));
                        out += buf;
                    }
                }
            }
        }

        void append_escaped_wide(std::string& out, const unsigned char* data, std::size_t count,
                                 uint32_t element_size)
        {
            for (std::size_t i = 0; i < count; ++i)
            {
                const unsigned char* p = data + i * element_size;
                const uint32_t w = element_size == 2 ? load<uint16_t>(p) : load<uint32_t>(p);
                if (w == 0)
                    break;
                char buf[16];
                if (w >= 0x20 && w <= 0x7E)
                {
                    if (w == '\'' || w == '"' || w == '?' || w == '\\')
                        out += '\\';
                    out += static_cast<char>(w);
                    continue;
                }
                switch (w)
                {
                    case '\a':
                        out += "\\a";
                        break;
                    case '\b':
                        out += "\\b";
                        break;
                    case '\f':
                        out += "\\f";
                        break;
                    case '\n':
                    case '\r':
                        out += "\\n";
                        break;
                    case '\t':
                        out += "\\t";
                        break;
                    case '\v':
                        out += "\\v";
                        break;
                    default:
                        if (w <= 0xFF)
                            std::snprintf(buf, sizeof buf, "\\x%02x", w);
                        else if (w <= 0xFFFF)
                            std::snprintf(buf, sizeof buf, "\\u%04X", w);
                        else
                            std::snprintf(buf, sizeof buf, "\\U%08X", w);
                        out += buf;
                }
            }
        }

        void append_ascii_value(std::string& out, const FieldDesc& desc, const unsigned char* data,
                                const Conversion* conversion, std::string_view units)
        {
            if (desc.text == Text::Narrow)
            {
                append_escaped_narrow(out, data, desc.count);
            }
            else if (desc.text == Text::Wide)
            {
                append_escaped_wide(out, data, desc.count, desc.element_size);
            }
            else if (desc.count > 0)
            {
                if (needs_c_locale(desc.type))
                {
                    ScopedCLocale c_locale;
                    for (uint32_t i = 0; i < desc.count; ++i)
                    {
                        if (i != 0)
                            out += ',';
                        append_element(out, desc, data + static_cast<std::size_t>(i) * desc.element_size, conversion);
                    }
                }
                else
                {
                    for (uint32_t i = 0; i < desc.count; ++i)
                    {
                        if (i != 0)
                            out += ',';
                        append_element(out, desc, data + static_cast<std::size_t>(i) * desc.element_size, conversion);
                    }
                }
            }

            if (!units.empty())
            {
                if (desc.units_dashdash)
                {
                    out += " {--}";
                }
                else
                {
                    out += " {";
                    out += units;
                    out += '}';
                }
            }
        }

    } // namespace vs
} // namespace Trick
