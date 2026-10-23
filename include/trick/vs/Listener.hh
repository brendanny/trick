/*
PURPOSE: (A TCP socket that accepts variable server clients.)
*/

#ifndef TRICK_VS_LISTENER_HH
#define TRICK_VS_LISTENER_HH

#include "trick/vs/Address.hh"
#include "trick/vs/Connection.hh"
#include "trick/vs/Endpoint.hh"
#include "trick/vs/Expected.hh"
#include "trick/vs/Fd.hh"

#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <string_view>

namespace Trick
{
    namespace vs
    {

        class Listener
        {
            public:
                /**
                 * Bind and listen. `requested` follows resolve_bind_address() with
                 * SocketKind::Tcp; port 0 lets the OS choose. The socket is
                 * non-blocking, close-on-exec, SO_REUSEADDR, and TCP_NODELAY for the
                 * clients it accepts. An IPv6 "::" socket also takes IPv4 clients.
                 */
                static Expected<Listener> open(SystemInterface& sys, std::string_view requested, uint16_t port);

                Listener(Listener&&) noexcept            = default;
                Listener& operator=(Listener&&) noexcept = default;

                int fd() const noexcept { return _fd.get(); }

                /** The bound address, with the port the OS chose. */
                const Address& address() const noexcept { return _address; }

                uint16_t port() const noexcept { return _address.port(); }

                /** The name the server reports: the host name for every interface, else as requested. */
                const std::string& hostname() const noexcept { return _hostname; }

                /** A client that was accepted, before the allowlist and connection checks. */
                struct Accepted
                {
                        Fd fd;
                        Address peer;
                };

                /**
                 * Accept one waiting client. Empty if there is none (EAGAIN) or it went
                 * away before it was accepted. An Error is a resource problem
                 * (EMFILE, ENOBUFS); the listener stays open.
                 */
                Expected<std::optional<Accepted>> accept();

                /** Accept one client and make it a TcpConnection. */
                Expected<std::unique_ptr<TcpConnection>> accept_connection(const ConnectionOptions& options = {});

                void close() noexcept { _fd.reset(); }

                bool is_open() const noexcept { return _fd.valid(); }

            private:
                Listener(Fd fd, Address address, std::string hostname)
                    : _fd(std::move(fd))
                    , _address(address)
                    , _hostname(std::move(hostname))
                {
                }

                Fd _fd;
                Address _address;
                std::string _hostname;
        };

    } // namespace vs
} // namespace Trick

#endif
