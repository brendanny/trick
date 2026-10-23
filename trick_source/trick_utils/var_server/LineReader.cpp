#include "trick/vs/LineReader.hh"

#include <algorithm>

namespace Trick
{
    namespace vs
    {

        void strip_carriage_returns(std::string& text)
        {
            text.erase(std::remove(text.begin(), text.end(), '\r'), text.end());
        }

        void LineReader::append(std::string_view bytes)
        {
            while (!bytes.empty())
            {
                if (_discarding)
                {
                    const std::size_t nl = bytes.find('\n');
                    if (nl == std::string_view::npos)
                    {
                        _discarded_report += bytes.size();
                        return;
                    }
                    _discarded_report += nl + 1;
                    bytes.remove_prefix(nl + 1);
                    _discarding = false;
                    continue;
                }
                // Hold at most `limit` bytes that have no newline after them.
                const std::size_t last_nl = _buffer.rfind('\n');
                const std::size_t tail    = last_nl == std::string::npos ? _buffer.size() : _buffer.size() - last_nl - 1;
                const std::size_t nl      = bytes.find('\n');
                const std::size_t run     = nl == std::string_view::npos ? bytes.size() : nl;
                if (tail + run > _limit)
                {
                    // This line is longer than the limit: drop what is held of it and
                    // the rest of it up to its newline.
                    _discarded_report += tail;
                    _buffer.resize(_buffer.size() - tail);
                    _discarding = true;
                    continue;
                }
                const std::size_t take = nl == std::string_view::npos ? bytes.size() : nl + 1;
                _buffer.append(bytes.data(), take);
                bytes.remove_prefix(take);
            }
        }

        bool LineReader::next_batch(std::string& batch)
        {
            // A line may hold `limit` characters, so its newline can be byte limit + 1.
            const std::size_t window = std::min(_buffer.size(), _limit + 1);
            if (window == 0)
                return false;
            const std::size_t nl = _buffer.rfind('\n', window - 1);
            if (nl == std::string::npos)
                return false;
            batch.assign(_buffer, 0, nl + 1);
            _buffer.erase(0, nl + 1);
            strip_carriage_returns(batch);
            return true;
        }

    } // namespace vs
} // namespace Trick
