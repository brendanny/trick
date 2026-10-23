#include "trick/vs/WriteQueue.hh"

namespace Trick
{
    namespace vs
    {

        bool WriteQueue::push(std::string_view message)
        {
            if (message.empty())
                return true;
            if (!fits(message.size()))
                return false;
            _messages.emplace_back(message);
            _bytes += message.size();
            return true;
        }

        void WriteQueue::consume(std::size_t bytes) noexcept
        {
            while (bytes > 0 && !_messages.empty())
            {
                const std::size_t left = _messages.front().size() - _offset;
                if (bytes < left)
                {
                    _offset += bytes;
                    _bytes -= bytes;
                    return;
                }
                bytes -= left;
                _bytes -= left;
                _messages.pop_front();
                _offset = 0;
            }
        }

        void WriteQueue::pop() noexcept
        {
            if (_messages.empty())
                return;
            _bytes -= _messages.front().size() - _offset;
            _messages.pop_front();
            _offset = 0;
        }

    } // namespace vs
} // namespace Trick
