/*
PURPOSE: (Wait for sockets, with a way for another thread to wake the wait.)

poll() plus a self-pipe: macOS has no eventfd, and poll() is on every
supported platform. wake() writes one byte to the pipe; it is safe from
any thread and from a signal handler.
*/

#ifndef TRICK_VS_POLLER_HH
#define TRICK_VS_POLLER_HH

#include "trick/vs/Expected.hh"
#include "trick/vs/Fd.hh"

#include <vector>

#include <poll.h>

namespace Trick
{
    namespace vs
    {

        class Poller
        {
            public:
                static Expected<Poller> create(SystemInterface& sys = system_interface());

                Poller(Poller&&) noexcept            = default;
                Poller& operator=(Poller&&) noexcept = default;

                /** Make the current or next wait() return at once. */
                void wake() const noexcept;

                /**
                 * Wait until one of `items` is ready, wake() is called, or `timeout_ms`
                 * pass (-1: no limit). Fills each item's revents. Returns true if it was
                 * woken (the wake is consumed). EINTR returns false with no events.
                 */
                Expected<bool> wait(std::vector<pollfd>& items, int timeout_ms);

            private:
                Poller(Fd read_end, Fd write_end)
                    : _read(std::move(read_end))
                    , _write(std::move(write_end))
                {
                }

                void drain() const noexcept;

                Fd _read;
                Fd _write;
                std::vector<pollfd> _scratch;
        };

    } // namespace vs
} // namespace Trick

#endif
