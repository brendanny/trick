/*
PURPOSE: (Helpers for the network tests: a SystemInterface with hooks, and plain client sockets.)
*/

#ifndef VS_TEST_NETTESTUTIL_HH
#define VS_TEST_NETTESTUTIL_HH

#include "trick/vs/Address.hh"
#include "trick/vs/SystemInterface.hh"

#include <cerrno>
#include <chrono>
#include <cstring>
#include <functional>
#include <string>
#include <thread>

#include <arpa/inet.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>

namespace vs_test
{
    using namespace Trick::vs;

    /** Calls the OS, except where a test sets a hook. A hook returns -1 with errno set to fail. */
    class HookedSystem : public SystemInterface
    {
        public:
            std::function<int(int, int, int)> on_socket;
            std::function<int(int, const sockaddr*, socklen_t)> on_bind;
            std::function<int(int, sockaddr*, socklen_t*)> on_accept;
            std::function<ssize_t(int, const void*, std::size_t, int)> on_send;
            std::function<ssize_t(int, void*, std::size_t, int)> on_recv;
            std::function<int(pollfd*, nfds_t, int)> on_poll;
            std::function<int(int[2])> on_pipe;
            std::string host_name = "testhost";
            int closes            = 0;

            int socket(int d, int t, int p) override { return on_socket ? on_socket(d, t, p) : SystemInterface::socket(d, t, p); }

            int bind(int fd, const sockaddr* a, socklen_t l) override
            {
                return on_bind ? on_bind(fd, a, l) : SystemInterface::bind(fd, a, l);
            }

            int accept(int fd, sockaddr* a, socklen_t* l) override
            {
                return on_accept ? on_accept(fd, a, l) : SystemInterface::accept(fd, a, l);
            }

            ssize_t send(int fd, const void* b, std::size_t n, int f) override
            {
                return on_send ? on_send(fd, b, n, f) : SystemInterface::send(fd, b, n, f);
            }

            ssize_t recv(int fd, void* b, std::size_t n, int f) override
            {
                return on_recv ? on_recv(fd, b, n, f) : SystemInterface::recv(fd, b, n, f);
            }

            int poll(pollfd* p, nfds_t n, int t) override { return on_poll ? on_poll(p, n, t) : SystemInterface::poll(p, n, t); }

            int pipe(int fds[2]) override { return on_pipe ? on_pipe(fds) : SystemInterface::pipe(fds); }

            int close(int fd) override
            {
                ++closes;
                return SystemInterface::close(fd);
            }

            std::string hostname() override { return host_name; }
    };

    inline int fail_with(int e)
    {
        errno = e;
        return -1;
    }

    /** A plain blocking TCP client, connected to `address`. -1 on failure. */
    inline int tcp_client(const Address& address)
    {
        const int fd = ::socket(address.family(), SOCK_STREAM, 0);
        if (fd < 0)
            return -1;
        if (::connect(fd, address.data(), address.length()) != 0)
        {
            ::close(fd);
            return -1;
        }
        return fd;
    }

    inline void send_all(int fd, const std::string& data)
    {
        std::size_t done = 0;
        while (done < data.size())
        {
            const ssize_t n = ::send(fd, data.data() + done, data.size() - done, MSG_NOSIGNAL);
            if (n <= 0)
                return;
            done += static_cast<std::size_t>(n);
        }
    }

    /** Wait up to `ms` for `fd` to be readable. */
    inline bool readable(int fd, int ms)
    {
        pollfd p { fd, POLLIN, 0 };
        return ::poll(&p, 1, ms) == 1;
    }

    /** Read what arrives within `ms`, up to `max` bytes. */
    inline std::string recv_for(int fd, int ms, std::size_t max = 1 << 20)
    {
        std::string out;
        const auto end = std::chrono::steady_clock::now() + std::chrono::milliseconds(ms);
        char buf[65536];
        while (out.size() < max)
        {
            const auto left = std::chrono::duration_cast<std::chrono::milliseconds>(end - std::chrono::steady_clock::now());
            if (left.count() <= 0 || !readable(fd, static_cast<int>(left.count())))
                break;
            const ssize_t n = ::recv(fd, buf, sizeof buf, 0);
            if (n <= 0)
                break;
            out.append(buf, static_cast<std::size_t>(n));
        }
        return out;
    }

    /** True if the peer closed `fd` within `ms` (recv returns 0 or an error). */
    inline bool closed_by_peer(int fd, int ms)
    {
        if (!readable(fd, ms))
            return false;
        char c;
        return ::recv(fd, &c, 1, 0) <= 0;
    }

    /** Call `f` until it returns true or `ms` pass. */
    template <class F> bool eventually(F f, int ms = 2000)
    {
        const auto end = std::chrono::steady_clock::now() + std::chrono::milliseconds(ms);
        while (std::chrono::steady_clock::now() < end)
        {
            if (f())
                return true;
            std::this_thread::sleep_for(std::chrono::milliseconds(2));
        }
        return f();
    }

    inline bool ipv6_loopback_available()
    {
        const int fd = ::socket(AF_INET6, SOCK_STREAM, 0);
        if (fd < 0)
            return false;
        sockaddr_in6 a {};
        a.sin6_family = AF_INET6;
        a.sin6_addr   = in6addr_loopback;
        const bool ok = ::bind(fd, reinterpret_cast<sockaddr*>(&a), sizeof a) == 0;
        ::close(fd);
        return ok;
    }

    /** A UDP socket bound to 127.0.0.1 on an OS-chosen port. */
    inline int udp_socket(Address* bound = nullptr)
    {
        const int fd = ::socket(AF_INET, SOCK_DGRAM, 0);
        auto a       = *Address::parse("127.0.0.1", 0);
        ::bind(fd, a.data(), a.length());
        if (bound)
        {
            socklen_t l = Address::capacity();
            ::getsockname(fd, bound->data(), &l);
            *bound = Address(bound->data(), l);
        }
        return fd;
    }

} // namespace vs_test

#endif
