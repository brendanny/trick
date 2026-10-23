/*
PURPOSE: (The short replies that are not variable lists.)

These are never byteswapped, as in the old server (rewrite decision 2):
binary numbers are in host byte order even when the client asked for
byteswap.
*/

#ifndef TRICK_VS_FIXEDREPLY_HH
#define TRICK_VS_FIXEDREPLY_HH

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>

namespace Trick
{
    namespace vs
    {

        /** var_exists. ASCII "1\t<0|1>\n"; binary int32 1 then one byte 0 or 1. */
        std::string var_exists_reply(bool exists, bool binary);

        /** var_send_list_size. ASCII "3\t<n>\n"; binary int32 {3, 0, n}. */
        std::string list_size_reply(int32_t count, bool binary);

        /**
         * var_get_stl_size. ASCII "6\t<n>\n", or "6\tBAD_REF\n" for no size;
         * binary int32 {6, n}, with n = 0 for no size. The size is an int32 on
         * the wire; a larger size is clamped.
         */
        std::string stl_size_reply(std::optional<int64_t> size, bool binary);

        /** The header before the bytes of a file (send_file and send_sie_*). Always ASCII. */
        std::string file_header(uint64_t size);

        /** The reply when a file cannot be opened. Always ASCII. */
        std::string file_missing_reply();

        /** Text from stdout (stream 1) or stderr (2): "4 <stream> <length>\n<text>". */
        std::string stdio_reply(int stream, std::string_view text);

        /**
         * A Python line failed (VS_IP_ERROR, sent only after var_send_ip_errors(True),
         * decision 3): "-1 <length>\n<text>", as stdio, in ASCII and binary mode.
         */
        std::string ip_error_reply(std::string_view text);

    } // namespace vs
} // namespace Trick

#endif
