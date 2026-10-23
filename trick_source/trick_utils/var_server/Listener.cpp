#include "trick/vs/Listener.hh"

#include <cerrno>

#include <netinet/in.h>
#include <netinet/tcp.h>

namespace Trick
{
    namespace vs
    {

        Expected<Listener> Listener::open(SystemInterface& sys, std::string_view requested, uint16_t port)
        {
            auto target = resolve_bind_address(sys, requested, port, SocketKind::Tcp);
            if (!target)
                return target.error();
            const Address& bind_to = target.value().address;

            Fd fd(sys.socket(bind_to.family(), SOCK_STREAM, 0), sys);
            if (!fd)
                return system_error("socket", errno);
            if (auto r = set_cloexec(fd); !r)
                return r.error();

            const int one = 1;
            if (sys.setsockopt(fd.get(), SOL_SOCKET, SO_REUSEADDR, &one, sizeof one) != 0)
                return system_error("setsockopt(SO_REUSEADDR)", errno);
            // Accepted sockets inherit this on Linux; TcpConnection::adopt sets it again.
            sys.setsockopt(fd.get(), IPPROTO_TCP, TCP_NODELAY, &one, sizeof one);
            if (bind_to.family() == AF_INET6 && bind_to.is_any())
            {
                const int zero = 0; // "::" takes IPv4 clients as well
                sys.setsockopt(fd.get(), IPPROTO_IPV6, IPV6_V6ONLY, &zero, sizeof zero);
            }

            if (sys.bind(fd.get(), bind_to.data(), bind_to.length()) != 0)
                return system_error(("bind " + bind_to.to_string()).c_str(), errno);

            Address bound;
            socklen_t length = Address::capacity();
            if (sys.getsockname(fd.get(), bound.data(), &length) != 0)
                return system_error("getsockname", errno);
            bound = Address(bound.data(), length);
            if (port != 0 && bound.port() != port)
                return Error { "bound port " + std::to_string(bound.port()) + ", not the requested port "
                               + std::to_string(port) };

            if (sys.listen(fd.get(), SOMAXCONN) != 0)
                return system_error(("listen on port " + std::to_string(bound.port())).c_str(), errno);
            if (auto r = set_nonblocking(fd, true); !r)
                return r.error();

            return Listener(std::move(fd), bound, target.value().hostname);
        }

        Expected<std::optional<Listener::Accepted>> Listener::accept()
        {
            if (!_fd)
                return Error { "the listener is closed" };
            while (true)
            {
                Address peer;
                socklen_t length = Address::capacity();
                const int client = _fd.sys().accept(_fd.get(), peer.data(), &length);
                if (client >= 0)
                {
                    Accepted a { Fd(client, _fd.sys()), Address(peer.data(), length).unmapped() };
                    return std::optional<Accepted>(std::move(a));
                }
                const int e = errno;
                if (e == EINTR)
                    continue;
                // No client, or one that left before accept(): nothing to do.
                if (e == EAGAIN || e == EWOULDBLOCK || e == ECONNABORTED || e == EPROTO)
                    return std::optional<Accepted>();
                return system_error("accept", e);
            }
        }

        Expected<std::unique_ptr<TcpConnection>> Listener::accept_connection(const ConnectionOptions& options)
        {
            auto a = accept();
            if (!a)
                return a.error();
            if (!a.value())
                return std::unique_ptr<TcpConnection>();
            return TcpConnection::adopt(std::move(a.value()->fd), a.value()->peer, options);
        }

    } // namespace vs
} // namespace Trick
