/*
PURPOSE: (Turn a requested source address into the address a socket binds to.)

The rules are the old server's (TCPClientListener::initialize and
UDPConnection::initialize), so input files keep working:

  * "", "localhost" or this host's name binds every interface (0.0.0.0),
    and the server reports this host's name.
  * "127.0.0.1" binds loopback only, for every socket kind (rewrite decision
    12). The old UDP and multicast code bound every interface for it.
  * A numeric IPv4 address binds that address and is reported as given.
  * A numeric IPv6 address binds an IPv6 socket (rewrite decision 6: IPv6 is
    turned on by the source address). "::" binds every interface, accepts
    IPv4 clients as well, and reports this host's name.
  * Any other name is looked up; the first IPv4 result is used, else the
    first IPv6 result. It is reported as given.
*/

#ifndef TRICK_VS_ENDPOINT_HH
#define TRICK_VS_ENDPOINT_HH

#include "trick/vs/Address.hh"
#include "trick/vs/Expected.hh"
#include "trick/vs/SystemInterface.hh"

#include <cstdint>
#include <string>
#include <string_view>

namespace Trick
{
    namespace vs
    {

        enum class SocketKind
        {
            Tcp,
            Udp ///< also multicast
        };

        struct BindTarget
        {
                Address address;      ///< what to bind, with the requested port
                std::string hostname; ///< what the server reports (beacon, var_server_get_hostname)
        };

        Expected<BindTarget> resolve_bind_address(SystemInterface& sys, std::string_view requested, uint16_t port,
                                                  SocketKind kind);

        /** Look up a host name or numeric address: the first IPv4 result, else the first IPv6 one. */
        Expected<Address> lookup_host(SystemInterface& sys, std::string_view name, uint16_t port);

    } // namespace vs
} // namespace Trick

#endif
