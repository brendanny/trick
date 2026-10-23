/*
PURPOSE: (A file descriptor that closes itself.)
*/

#ifndef TRICK_VS_FD_HH
#define TRICK_VS_FD_HH

#include "trick/vs/Expected.hh"
#include "trick/vs/SystemInterface.hh"

namespace Trick
{
    namespace vs
    {

        /**
         * Owns one file descriptor and closes it through its SystemInterface.
         * Move-only. An empty Fd holds -1.
         */
        class Fd
        {
            public:
                Fd() noexcept = default;

                explicit Fd(int fd, SystemInterface& sys = system_interface()) noexcept
                    : _fd(fd)
                    , _sys(&sys)
                {
                }

                Fd(Fd&& other) noexcept
                    : _fd(other._fd)
                    , _sys(other._sys)
                {
                    other._fd = -1;
                }

                Fd& operator=(Fd&& other) noexcept
                {
                    if (this != &other)
                    {
                        reset();
                        _fd       = other._fd;
                        _sys      = other._sys;
                        other._fd = -1;
                    }
                    return *this;
                }

                Fd(const Fd&)            = delete;
                Fd& operator=(const Fd&) = delete;

                ~Fd() { reset(); }

                int get() const noexcept { return _fd; }

                bool valid() const noexcept { return _fd >= 0; }

                explicit operator bool() const noexcept { return valid(); }

                SystemInterface& sys() const noexcept { return *_sys; }

                /** Give up ownership without closing. */
                int release() noexcept
                {
                    const int fd = _fd;
                    _fd          = -1;
                    return fd;
                }

                /** Close the descriptor, if any. */
                void reset() noexcept;

            private:
                int _fd               = -1;
                SystemInterface* _sys = &system_interface();
        };

        /** Set O_NONBLOCK on or off. */
        Expected<void> set_nonblocking(const Fd& fd, bool on);

        /** Set FD_CLOEXEC, so a child process started with system() does not keep the socket. */
        Expected<void> set_cloexec(const Fd& fd);

        /** An Error that names `what` and the text of `error` (an errno value). */
        Error system_error(const char* what, int error);

    } // namespace vs
} // namespace Trick

#endif
