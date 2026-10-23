/*
PURPOSE: (Split a client's byte stream into command batches.)

A batch is every complete line the client has sent so far: the bytes up to
and including the last newline, with each '\r' removed, as the old server
read them (TCPConnection::read). The parser treats one batch as one unit.

The old server peeked at most 200000 bytes and waited for a newline in
them. A longer line with no newline stalled the session for good. Here a
line longer than the limit is discarded up to its newline, the session gets
a message for its log, and the lines after it run as usual.
*/

#ifndef TRICK_VS_LINEREADER_HH
#define TRICK_VS_LINEREADER_HH

#include <cstddef>
#include <string>
#include <string_view>

namespace Trick
{
    namespace vs
    {

        class LineReader
        {
            public:
                /** The old MAX_CMD_LEN. */
                static constexpr std::size_t default_limit = 200000;

                explicit LineReader(std::size_t limit = default_limit) noexcept
                    : _limit(limit)
                {
                }

                /** Add bytes as they arrive. */
                void append(std::string_view bytes);

                /**
                 * Take the next batch: the complete lines in the first `limit` + 1
                 * bytes held, '\r' removed. Returns false if there is no complete line.
                 */
                bool next_batch(std::string& batch);

                /**
                 * Bytes discarded since the last call (a line longer than the limit),
                 * and reset the count. 0 if nothing was discarded.
                 */
                std::size_t take_discarded() noexcept
                {
                    const std::size_t n = _discarded_report;
                    _discarded_report   = 0;
                    return n;
                }

                /** Bytes held that are not yet a complete line. */
                std::size_t pending() const noexcept { return _buffer.size(); }

                /** True while the rest of an overlong line is being discarded. */
                bool discarding() const noexcept { return _discarding; }

                std::size_t limit() const noexcept { return _limit; }

                void clear() noexcept
                {
                    _buffer.clear();
                    _discarding = false;
                }

            private:
                std::size_t _limit;
                std::string _buffer;
                bool _discarding             = false;
                std::size_t _discarded_report = 0;
        };

        /** Remove every '\r' from `text`. */
        void strip_carriage_returns(std::string& text);

    } // namespace vs
} // namespace Trick

#endif
