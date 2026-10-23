#include "trick/vs/Connection.hh"

#include "trick/vs/Endpoint.hh"

#include <cerrno>
#include <cstring>

#include <netinet/in.h>
#include <netinet/tcp.h>

namespace Trick
{
    namespace vs
    {

        namespace
        {
#ifdef MSG_NOSIGNAL
            constexpr int send_flags = MSG_NOSIGNAL;
#else
            constexpr int send_flags = 0; // SO_NOSIGPIPE is set on the socket instead
#endif

            bool would_block(int e) noexcept { return e == EAGAIN || e == EWOULDBLOCK; }

            std::string number(std::size_t n) { return std::to_string(n); }

            /** Socket options every client socket gets. */
            void client_socket_options([[maybe_unused]] const Fd& fd)
            {
#ifdef SO_NOSIGPIPE
                const int one = 1;
                fd.sys().setsockopt(fd.get(), SOL_SOCKET, SO_NOSIGPIPE, &one, sizeof one);
#endif
            }

            Address local_address(const Fd& fd)
            {
                Address a;
                socklen_t length = Address::capacity();
                if (fd.sys().getsockname(fd.get(), a.data(), &length) != 0)
                    return Address();
                return Address(a.data(), length);
            }

            /** Bind a datagram socket by the UDP rules. */
            Expected<Fd> open_datagram(SystemInterface& sys, const Address& bind_to)
            {
                Fd fd(sys.socket(bind_to.family(), SOCK_DGRAM, 0), sys);
                if (!fd)
                    return system_error("socket", errno);
                if (auto r = set_cloexec(fd); !r)
                    return r.error();
                const int one = 1;
                if (sys.setsockopt(fd.get(), SOL_SOCKET, SO_REUSEADDR, &one, sizeof one) != 0)
                    return system_error("setsockopt(SO_REUSEADDR)", errno);
                client_socket_options(fd);
                if (sys.bind(fd.get(), bind_to.data(), bind_to.length()) != 0)
                    return system_error(("bind " + bind_to.to_string()).c_str(), errno);
                if (auto r = set_nonblocking(fd, true); !r)
                    return r.error();
                return fd;
            }

            Expected<void> check_port(const Address& bound, uint16_t requested)
            {
                if (requested != 0 && bound.port() != requested)
                    return Error { "bound port " + std::to_string(bound.port()) + ", not the requested port "
                                   + std::to_string(requested) };
                return {};
            }
        } // namespace

        const char* connection_kind_name(ConnectionKind kind) noexcept
        {
            switch (kind)
            {
                case ConnectionKind::Tcp:
                    return "TCP";
                case ConnectionKind::Udp:
                    return "UDP";
                case ConnectionKind::Multicast:
                    return "multicast";
            }
            return "unknown";
        }

        Connection::~Connection() { close(); }

        void Connection::close() noexcept
        {
            if (_fd.valid())
            {
                sys().shutdown(_fd.get(), SHUT_RDWR);
                _fd.reset();
            }
            _queue.clear();
        }

        // ------------------------------------------------------------------
        // TCP
        // ------------------------------------------------------------------

        Expected<std::unique_ptr<TcpConnection>> TcpConnection::adopt(Fd fd, const Address& peer,
                                                                      const ConnectionOptions& options)
        {
            if (!fd)
                return Error { "no socket to adopt" };
            if (auto r = set_cloexec(fd); !r)
                return r.error();
            if (auto r = set_nonblocking(fd, true); !r)
                return r.error();
            const int one = 1;
            // Replies are small and latency matters more than throughput.
            fd.sys().setsockopt(fd.get(), IPPROTO_TCP, TCP_NODELAY, &one, sizeof one);
            client_socket_options(fd);
            const Address local = local_address(fd);
            return std::unique_ptr<TcpConnection>(new TcpConnection(std::move(fd), local, peer.unmapped(), options));
        }

        ReadResult TcpConnection::read(std::string& batch)
        {
            ReadResult r;
            if (!_fd.valid())
            {
                r.status = ReadResult::Status::Closed;
                return r;
            }
            auto discarded_note = [this, &r] {
                if (const std::size_t n = _reader.take_discarded())
                    r.note = "discarded " + number(n) + " bytes: a command line longer than "
                           + number(_reader.limit()) + " bytes";
            };

            if (_reader.next_batch(batch))
            {
                r.status = ReadResult::Status::Batch;
                return r;
            }

            if (!_eof)
            {
                char buffer[65536];
                std::size_t total = 0;
                while (total < (1u << 20)) // at most 1 MiB per call, so other work is not starved
                {
                    const ssize_t n = sys().recv(_fd.get(), buffer, sizeof buffer, 0);
                    if (n > 0)
                    {
                        _reader.append(std::string_view(buffer, static_cast<std::size_t>(n)));
                        total += static_cast<std::size_t>(n);
                        if (static_cast<std::size_t>(n) < sizeof buffer)
                            break;
                        continue;
                    }
                    if (n == 0)
                    {
                        _eof = true;
                        break;
                    }
                    const int e = errno;
                    if (e == EINTR)
                        continue;
                    if (would_block(e))
                        break;
                    if (e == ECONNRESET)
                    {
                        _eof = true;
                        break;
                    }
                    r.status = ReadResult::Status::Error;
                    r.note   = "recv: " + errno_text(e);
                    return r;
                }
            }

            discarded_note();
            if (_reader.next_batch(batch))
            {
                r.status = ReadResult::Status::Batch;
                return r;
            }
            if (_eof)
            {
                r.status = ReadResult::Status::Closed;
                if (_reader.pending() > 0)
                    r.note = "the client closed the connection with " + number(_reader.pending())
                           + " bytes after its last newline; they were not run";
                return r;
            }
            r.status = ReadResult::Status::Nothing;
            return r;
        }

        FlushResult TcpConnection::flush()
        {
            FlushResult r;
            while (!_queue.empty())
            {
                if (!_fd.valid())
                {
                    r.status = FlushResult::Status::Error;
                    r.note   = "the connection is closed";
                    return r;
                }
                const std::string_view data = _queue.front();
                const ssize_t n             = sys().send(_fd.get(), data.data(), data.size(), send_flags);
                if (n >= 0)
                {
                    _queue.consume(static_cast<std::size_t>(n));
                    continue;
                }
                const int e = errno;
                if (e == EINTR)
                    continue;
                if (would_block(e))
                {
                    r.status = FlushResult::Status::Pending;
                    return r;
                }
                r.status        = FlushResult::Status::Error;
                r.client_closed = (e == EPIPE || e == ECONNRESET);
                r.note          = (r.client_closed ? "the client closed the connection during a reply (send: "
                                                   : "send: ")
                       + errno_text(e) + (r.client_closed ? ")" : "");
                return r;
            }
            return r;
        }

        // ------------------------------------------------------------------
        // UDP
        // ------------------------------------------------------------------

        Expected<std::unique_ptr<UdpConnection>> UdpConnection::open(SystemInterface& sys, std::string_view requested,
                                                                     uint16_t port, const ConnectionOptions& options)
        {
            auto target = resolve_bind_address(sys, requested, port, SocketKind::Udp);
            if (!target)
                return target.error();
            auto fd = open_datagram(sys, target.value().address);
            if (!fd)
                return fd.error();
            const Address local = local_address(fd.value());
            if (auto r = check_port(local, port); !r)
                return r.error();
            return std::unique_ptr<UdpConnection>(
                new UdpConnection(std::move(fd.value()), local, target.value().hostname, options));
        }

        ReadResult UdpConnection::read(std::string& batch)
        {
            ReadResult r;
            if (!_fd.valid())
            {
                r.status = ReadResult::Status::Closed;
                return r;
            }
            char buffer[65536];
            // Skip at most this many of our own datagrams per call.
            for (int tries = 0; tries < 64; ++tries)
            {
                Address sender;
                socklen_t length = Address::capacity();
                const ssize_t n  = sys().recvfrom(_fd.get(), buffer, sizeof buffer, 0, sender.data(), &length);
                if (n < 0)
                {
                    const int e = errno;
                    if (e == EINTR || e == ECONNREFUSED) // ECONNREFUSED: an ICMP reply to an earlier sendto
                        continue;
                    if (would_block(e))
                        return r;
                    r.status = ReadResult::Status::Error;
                    r.note   = "recvfrom: " + errno_text(e);
                    return r;
                }
                sender = Address(sender.data(), length).unmapped();
                if (is_own(sender))
                    continue;
                if (_filter && !_filter(sender))
                {
                    r.note = "ILLEGAL IP: dropped a datagram from " + sender.host();
                    return r;
                }
                const std::string_view data(buffer, static_cast<std::size_t>(n));
                const std::size_t nl = data.rfind('\n');
                if (nl == std::string_view::npos)
                {
                    r.note = "dropped a datagram of " + number(data.size()) + " bytes from " + sender.host()
                           + ": it has no newline";
                    return r;
                }
                if (nl + 1 != data.size())
                    r.note = "dropped " + number(data.size() - nl - 1) + " bytes after the last newline of a datagram from "
                           + sender.host();
                batch.assign(data.data(), nl + 1);
                strip_carriage_returns(batch);
                if (reply_to_sender())
                    _reply_to = sender;
                r.status = ReadResult::Status::Batch;
                return r;
            }
            return r;
        }

        FlushResult UdpConnection::flush()
        {
            FlushResult r;
            std::size_t failed = 0;
            std::string last_error;
            while (!_queue.empty())
            {
                if (!_fd.valid())
                {
                    r.status = FlushResult::Status::Error;
                    r.note   = "the connection is closed";
                    return r;
                }
                if (_reply_to.empty())
                {
                    r.note = "dropped " + number(_queue.messages()) + " messages: no client has sent a command yet";
                    _queue.clear();
                    return r;
                }
                const std::string_view data = _queue.front();
                const ssize_t n = sys().sendto(send_fd(), data.data(), data.size(), send_flags, _reply_to.data(),
                                               _reply_to.length());
                if (n >= 0)
                {
                    _queue.pop();
                    continue;
                }
                const int e = errno;
                if (e == EINTR)
                    continue;
                if (would_block(e))
                {
                    r.status = FlushResult::Status::Pending;
                    break;
                }
                // Datagrams are best effort: drop this one and go on.
                ++failed;
                last_error = errno_text(e);
                _queue.pop();
            }
            if (failed != 0)
                r.note = "dropped " + number(failed) + " datagrams to " + _reply_to.to_string() + ": " + last_error;
            return r;
        }

        // ------------------------------------------------------------------
        // Multicast
        // ------------------------------------------------------------------

        Expected<std::unique_ptr<MulticastConnection>> MulticastConnection::open(SystemInterface& sys,
                                                                                 std::string_view group_text,
                                                                                 std::string_view requested,
                                                                                 uint16_t port,
                                                                                 const ConnectionOptions& options)
        {
            auto group = Address::parse(group_text, port);
            if (!group || !group->is_multicast())
                return Error { "[" + std::string(group_text) + "] is not a multicast address" };

            auto target = resolve_bind_address(sys, requested, port, SocketKind::Udp);
            if (!target)
                return target.error();
            Address bind_to = target.value().address;
            if (bind_to.family() != group->family())
            {
                if (!bind_to.is_any())
                    return Error { "the multicast group and the source address are not the same IP version" };
                bind_to = Address::any(group->family(), port);
            }

            auto fd = open_datagram(sys, bind_to);
            if (!fd)
                return fd.error();
            const Fd& s = fd.value();

            auto multicast_options = [&sys](const Fd& socket, int family) {
                const int one = 1;
                if (family == AF_INET)
                {
#ifdef IP_MULTICAST_ALL
                    // Linux delivers a group's datagrams to every socket on the port unless
                    // this is off. The server sends to the group; it never reads from it.
                    const int zero = 0;
                    sys.setsockopt(socket.get(), IPPROTO_IP, IP_MULTICAST_ALL, &zero, sizeof zero);
#endif
                    const unsigned char loop = 1; // local clients listen to the group too
                    sys.setsockopt(socket.get(), IPPROTO_IP, IP_MULTICAST_LOOP, &loop, sizeof loop);
                }
                else
                {
                    sys.setsockopt(socket.get(), IPPROTO_IPV6, IPV6_MULTICAST_LOOP, &one, sizeof one);
                }
            };
            multicast_options(s, group->family());

            // Decision 12: bound to loopback, the socket takes commands only from this
            // host. It cannot reach the group (loopback has no multicast), so replies
            // leave from a second socket bound to no address.
            Fd sender;
            if (bind_to.is_loopback())
            {
                auto opened = open_datagram(sys, Address::any(group->family(), 0));
                if (!opened)
                    return opened.error();
                sender = std::move(opened.value());
                multicast_options(sender, group->family());
            }

            const Address local = local_address(s);
            if (auto r = check_port(local, port); !r)
                return r.error();
            group->set_port(local.port()); // replies go to the group on the bound port

            // The hosts our own datagrams can come from: the bound address, or every
            // interface when bound to all of them.
            std::vector<Address> own;
            if (local.is_any())
                own = sys.local_addresses();
            else
                own.push_back(local);

            if (sender)
            {
                // Its datagrams leave from this host's interfaces.
                const std::vector<Address> all = sys.local_addresses();
                own.insert(own.end(), all.begin(), all.end());
            }

            return std::unique_ptr<MulticastConnection>(new MulticastConnection(std::move(fd.value()), std::move(sender),
                                                                                local, target.value().hostname, *group,
                                                                                std::move(own), options));
        }

        Address MulticastConnection::send_address() const
        {
            if (!_sender)
                return _local;
            Address a;
            socklen_t length = Address::capacity();
            if (sys().getsockname(_sender.get(), a.data(), &length) != 0)
                return Address();
            return Address(a.data(), length);
        }

        bool MulticastConnection::is_own(const Address& sender) const
        {
            const uint16_t send_port = _sender ? send_address().port() : _local.port();
            if (sender.port() != _local.port() && sender.port() != send_port)
                return false;
            if (sender.is_loopback())
                return true;
            for (const Address& a : _own_hosts)
                if (a.same_host(sender))
                    return true;
            return false;
        }

    } // namespace vs
} // namespace Trick
