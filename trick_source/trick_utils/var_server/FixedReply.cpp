#include "trick/vs/FixedReply.hh"

#include "trick/vs/WireTypes.hh"

#include <charconv>
#include <cstring>
#include <limits>

namespace Trick
{
    namespace vs
    {

        namespace
        {

            template <class T> void append_number(std::string& out, T v)
            {
                char buf[24];
                const auto r = std::to_chars(buf, buf + sizeof buf, v);
                out.append(buf, r.ptr);
            }

            /** Host byte order, never swapped (rewrite decision 2). */
            void append_raw_int32(std::string& out, int32_t v)
            {
                char b[4];
                std::memcpy(b, &v, 4);
                out.append(b, 4);
            }

            std::string ascii(MessageType type)
            {
                std::string out;
                append_number(out, static_cast<int32_t>(type));
                out += '\t';
                return out;
            }

        } // namespace

        std::string var_exists_reply(bool exists, bool binary)
        {
            std::string out;
            if (binary)
            {
                append_raw_int32(out, static_cast<int32_t>(MessageType::VarExists));
                out += static_cast<char>(exists ? 1 : 0);
            }
            else
            {
                out = ascii(MessageType::VarExists);
                out += exists ? "1\n" : "0\n";
            }
            return out;
        }

        std::string list_size_reply(int32_t count, bool binary)
        {
            std::string out;
            if (binary)
            {
                append_raw_int32(out, static_cast<int32_t>(MessageType::ListSize));
                append_raw_int32(out, 0);
                append_raw_int32(out, count);
            }
            else
            {
                out = ascii(MessageType::ListSize);
                append_number(out, count);
                out += '\n';
            }
            return out;
        }

        std::string stl_size_reply(std::optional<int64_t> size, bool binary)
        {
            int32_t n = 0;
            if (size)
            {
                if (*size > std::numeric_limits<int32_t>::max())
                    n = std::numeric_limits<int32_t>::max();
                else if (*size < 0)
                    n = 0;
                else
                    n = static_cast<int32_t>(*size);
            }
            std::string out;
            if (binary)
            {
                append_raw_int32(out, static_cast<int32_t>(MessageType::StlSize));
                append_raw_int32(out, n);
            }
            else
            {
                out = ascii(MessageType::StlSize);
                if (size)
                    append_number(out, n);
                else
                    out += "BAD_REF";
                out += '\n';
            }
            return out;
        }

        std::string file_header(uint64_t size)
        {
            std::string out = ascii(MessageType::SieResource);
            append_number(out, size);
            out += '\n';
            return out;
        }

        std::string file_missing_reply() { return ascii(MessageType::SieResource) + "-1\n"; }

        std::string stdio_reply(int stream, std::string_view text)
        {
            std::string out;
            append_number(out, static_cast<int32_t>(MessageType::Stdio));
            out += ' ';
            append_number(out, stream);
            out += ' ';
            append_number(out, text.size());
            out += '\n';
            out += text;
            return out;
        }

    } // namespace vs
} // namespace Trick
