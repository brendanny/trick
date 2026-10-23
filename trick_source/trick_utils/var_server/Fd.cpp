#include "trick/vs/Fd.hh"

#include <cerrno>

#include <fcntl.h>

namespace Trick
{
    namespace vs
    {

        void Fd::reset() noexcept
        {
            if (_fd >= 0)
            {
                // close() may fail with EINTR; the descriptor is released either way
                // on Linux and macOS, so it is never retried.
                _sys->close(_fd);
                _fd = -1;
            }
        }

        Error system_error(const char* what, int error)
        {
            return Error { std::string(what) + ": " + errno_text(error) };
        }

        Expected<void> set_nonblocking(const Fd& fd, bool on)
        {
            const int flags = fd.sys().fcntl(fd.get(), F_GETFL, 0);
            if (flags < 0)
                return system_error("fcntl(F_GETFL)", errno);
            const int wanted = on ? (flags | O_NONBLOCK) : (flags & ~O_NONBLOCK);
            if (wanted != flags && fd.sys().fcntl(fd.get(), F_SETFL, wanted) < 0)
                return system_error("fcntl(F_SETFL)", errno);
            return {};
        }

        Expected<void> set_cloexec(const Fd& fd)
        {
            const int flags = fd.sys().fcntl(fd.get(), F_GETFD, 0);
            if (flags < 0)
                return system_error("fcntl(F_GETFD)", errno);
            if (fd.sys().fcntl(fd.get(), F_SETFD, flags | FD_CLOEXEC) < 0)
                return system_error("fcntl(F_SETFD)", errno);
            return {};
        }

    } // namespace vs
} // namespace Trick
