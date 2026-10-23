#include "trick/vs/Endpoint.hh"

#include <cstring>

namespace Trick
{
    namespace vs
    {

        Expected<Address> lookup_host(SystemInterface& sys, std::string_view name, uint16_t port)
        {
            if (auto numeric = Address::parse(name, port))
                return *numeric;

            addrinfo hints;
            std::memset(&hints, 0, sizeof hints);
            hints.ai_family   = AF_UNSPEC;
            hints.ai_socktype = SOCK_DGRAM;
            addrinfo* list    = nullptr;
            const std::string host(name);
            const int rc = sys.getaddrinfo(host.c_str(), nullptr, &hints, &list);
            if (rc != 0 || list == nullptr)
                return Error { "cannot find the address of [" + host + "]: " + gai_strerror(rc) };

            Address found;
            for (int want : { AF_INET, AF_INET6 })
            {
                for (addrinfo* p = list; p != nullptr && found.empty(); p = p->ai_next)
                    if (p->ai_family == want)
                        found = Address(p->ai_addr, p->ai_addrlen);
                if (!found.empty())
                    break;
            }
            sys.freeaddrinfo(list);
            if (found.empty())
                return Error { "[" + host + "] has no IPv4 or IPv6 address" };
            found.set_port(port);
            return found;
        }

        Expected<BindTarget> resolve_bind_address(SystemInterface& sys, std::string_view requested, uint16_t port,
                                                  SocketKind kind)
        {
            const std::string host_name = sys.hostname();
            BindTarget t;

            // Decision 12: "127.0.0.1" binds loopback for every socket kind. The old UDP
            // code bound every interface for it. `kind` is kept for future rules.
            (void)kind;
            if (requested.empty() || requested == "localhost" || (!host_name.empty() && requested == host_name))
            {
                t.address  = Address::any(AF_INET, port);
                t.hostname = host_name;
                return t;
            }

            if (auto numeric = Address::parse(requested, port))
            {
                t.address = *numeric;
                // "::" is new (IPv6); report the host name, which a client can use.
                t.hostname = (numeric->family() == AF_INET6 && numeric->is_any()) ? host_name : std::string(requested);
                return t;
            }

            auto found = lookup_host(sys, requested, port);
            if (!found)
                return found.error();
            t.address  = found.value();
            t.hostname = std::string(requested);
            return t;
        }

    } // namespace vs
} // namespace Trick
