/*
PURPOSE: (Bytes waiting to go to one client.)

The old server sent on a non-blocking socket and dropped the client on the
first EAGAIN. Here messages wait in a bounded queue and go out as the socket
takes them. Only when the queue is full is the client dropped.

Messages keep their boundaries, so a datagram socket can send one message
per sendto(), and a stream socket can send several in one send().
*/

#ifndef TRICK_VS_WRITEQUEUE_HH
#define TRICK_VS_WRITEQUEUE_HH

#include <cstddef>
#include <deque>
#include <string>
#include <string_view>

namespace Trick
{
    namespace vs
    {

        class WriteQueue
        {
            public:
                static constexpr std::size_t default_capacity = 16u << 20; // 16 MiB

                explicit WriteQueue(std::size_t capacity = default_capacity) noexcept
                    : _capacity(capacity)
                {
                }

                /** Add a message. False, and nothing added, if it would pass the capacity. */
                bool push(std::string_view message);

                /** True if `bytes` more would fit. */
                bool fits(std::size_t bytes) const noexcept { return bytes <= _capacity - _bytes; }

                bool empty() const noexcept { return _messages.empty(); }

                /** Bytes waiting, counting only what has not been sent. */
                std::size_t size() const noexcept { return _bytes; }

                std::size_t capacity() const noexcept { return _capacity; }

                std::size_t space() const noexcept { return _capacity - _bytes; }

                std::size_t messages() const noexcept { return _messages.size(); }

                /** The unsent part of the first message. Precondition: !empty(). */
                std::string_view front() const noexcept
                {
                    return std::string_view(_messages.front()).substr(_offset);
                }

                /** Mark `bytes` of the queue as sent, across messages if a stream sent more than one. */
                void consume(std::size_t bytes) noexcept;

                /** Drop the first message whole (a datagram that was sent, or could not be). */
                void pop() noexcept;

                void clear() noexcept
                {
                    _messages.clear();
                    _offset = 0;
                    _bytes  = 0;
                }

            private:
                std::size_t _capacity;
                std::deque<std::string> _messages;
                std::size_t _offset = 0; ///< bytes of the first message already sent
                std::size_t _bytes  = 0;
        };

    } // namespace vs
} // namespace Trick

#endif
