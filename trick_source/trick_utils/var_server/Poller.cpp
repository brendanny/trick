#include "trick/vs/Poller.hh"

#include <cerrno>

namespace Trick
{
    namespace vs
    {

        Expected<Poller> Poller::create(SystemInterface& sys)
        {
            int fds[2] = { -1, -1 };
            if (sys.pipe(fds) != 0)
                return system_error("pipe", errno);
            Fd read_end(fds[0], sys);
            Fd write_end(fds[1], sys);
            for (const Fd* fd : { &read_end, &write_end })
            {
                if (auto r = set_cloexec(*fd); !r)
                    return r.error();
                if (auto r = set_nonblocking(*fd, true); !r)
                    return r.error();
            }
            return Poller(std::move(read_end), std::move(write_end));
        }

        void Poller::wake() const noexcept
        {
            const char byte = 1;
            // A full pipe already holds a wake-up, so EAGAIN needs nothing more.
            while (_write.sys().write(_write.get(), &byte, 1) < 0 && errno == EINTR)
            {
            }
        }

        void Poller::drain() const noexcept
        {
            char buffer[256];
            while (true)
            {
                const ssize_t n = _read.sys().read(_read.get(), buffer, sizeof buffer);
                if (n > 0)
                    continue;
                if (n < 0 && errno == EINTR)
                    continue;
                return;
            }
        }

        Expected<bool> Poller::wait(std::vector<pollfd>& items, int timeout_ms)
        {
            _scratch.clear();
            _scratch.reserve(items.size() + 1);
            _scratch.push_back(pollfd { _read.get(), POLLIN, 0 });
            for (pollfd& p : items)
            {
                p.revents = 0;
                _scratch.push_back(p);
            }

            const int n = _read.sys().poll(_scratch.data(), static_cast<nfds_t>(_scratch.size()), timeout_ms);
            if (n < 0)
            {
                if (errno == EINTR)
                    return false;
                return system_error("poll", errno);
            }
            for (std::size_t i = 0; i < items.size(); ++i)
                items[i].revents = _scratch[i + 1].revents;
            const bool woken = (_scratch[0].revents & POLLIN) != 0;
            if (woken)
                drain();
            return woken;
        }

    } // namespace vs
} // namespace Trick
