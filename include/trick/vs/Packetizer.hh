/*
PURPOSE: (Split a list of values into messages of at most 8192 bytes.)

The rules are the old server's (VariableServerSession_write_data.cpp):

ASCII: the message type, then "\t" and the text of each value, then "\n".
A value longer than 8190 characters is cut to 8190. When the next value
would not fit, the message so far is sent as it is (it ends with the "\t"
for that value) and the value starts a new message with no type.

Binary: a 12-byte header (message type, size of the rest + 8, number of
values), then the values. A value that cannot fit in a message by itself is
skipped with a warning. When the next value would not fit, a new message
starts with its own header.

An empty list sends nothing.
*/

#ifndef TRICK_VS_PACKETIZER_HH
#define TRICK_VS_PACKETIZER_HH

#include "trick/vs/Interfaces.hh"
#include "trick/vs/Snapshot.hh"
#include "trick/vs/WireTypes.hh"

#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

namespace Trick
{
    namespace vs
    {

        /** The largest message the server sends, and the largest it reads. */
        constexpr std::size_t max_message = 8192;

        /** How to write one value of a Snapshot. */
        struct VarFormat
        {
                /** The name as the client sent it. Binary messages carry it. */
                std::string_view name;
                /** ASCII only: the conversion to the requested units, or null. */
                const Conversion* conversion = nullptr;
                /** ASCII only: the requested units, or empty for no " {units}". */
                std::string_view units;
        };

        /** The messages to send, in order, and warnings for the session log. */
        struct Packets
        {
                std::vector<std::string> messages;
                std::vector<std::string> warnings;

                void clear() noexcept
                {
                    messages.clear();
                    warnings.clear();
                }
        };

        /**
         * Encode the values of `snapshot` as ASCII messages. `formats` has one
         * entry per value. Throws std::invalid_argument if the sizes differ.
         * Appends to `out`.
         */
        void encode_ascii(Packets& out, const Snapshot& snapshot, const std::vector<VarFormat>& formats,
                          MessageType type);

        /** Encode the values of `snapshot` as binary messages. Appends to `out`. */
        void encode_binary(Packets& out, const Snapshot& snapshot, const std::vector<VarFormat>& formats,
                           MessageType type, bool nonames, bool byteswap);

    } // namespace vs
} // namespace Trick

#endif
