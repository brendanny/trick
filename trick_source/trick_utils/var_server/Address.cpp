#include "trick/vs/Address.hh"

#include <charconv>
#include <cstring>

#include <arpa/inet.h>

namespace Trick
{
    namespace vs
    {

        namespace
        {
            const sockaddr_in& v4(const sockaddr_storage& s) { return reinterpret_cast<const sockaddr_in&>(s); }

            const sockaddr_in6& v6(const sockaddr_storage& s) { return reinterpret_cast<const sockaddr_in6&>(s); }

            sockaddr_in& v4(sockaddr_storage& s) { return reinterpret_cast<sockaddr_in&>(s); }

            sockaddr_in6& v6(sockaddr_storage& s) { return reinterpret_cast<sockaddr_in6&>(s); }

            const unsigned char v4_mapped_prefix[12] = { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xFF, 0xFF };
        } // namespace

        Address::Address() noexcept
        {
            std::memset(&_storage, 0, sizeof _storage);
            _storage.ss_family = AF_UNSPEC;
        }

        Address::Address(const sockaddr* address, socklen_t length) noexcept
            : Address()
        {
            if (address == nullptr)
                return;
            if (address->sa_family == AF_INET && length >= static_cast<socklen_t>(sizeof(sockaddr_in)))
                std::memcpy(&_storage, address, sizeof(sockaddr_in));
            else if (address->sa_family == AF_INET6 && length >= static_cast<socklen_t>(sizeof(sockaddr_in6)))
                std::memcpy(&_storage, address, sizeof(sockaddr_in6));
        }

        std::optional<Address> Address::parse(std::string_view text, uint16_t port)
        {
            std::string s(text);
            // Accept "[::1]" as well as "::1".
            if (s.size() >= 2 && s.front() == '[' && s.back() == ']')
                s = s.substr(1, s.size() - 2);
            Address a;
            if (inet_pton(AF_INET, s.c_str(), &v4(a._storage).sin_addr) == 1)
            {
                v4(a._storage).sin_family = AF_INET;
                v4(a._storage).sin_port   = htons(port);
                return a;
            }
            if (inet_pton(AF_INET6, s.c_str(), &v6(a._storage).sin6_addr) == 1)
            {
                v6(a._storage).sin6_family = AF_INET6;
                v6(a._storage).sin6_port   = htons(port);
                return a;
            }
            return std::nullopt;
        }

        Address Address::any(int family, uint16_t port) noexcept
        {
            Address a;
            if (family == AF_INET6)
            {
                v6(a._storage).sin6_family = AF_INET6;
                v6(a._storage).sin6_addr   = in6addr_any;
                v6(a._storage).sin6_port   = htons(port);
            }
            else
            {
                v4(a._storage).sin_family      = AF_INET;
                v4(a._storage).sin_addr.s_addr = htonl(INADDR_ANY);
                v4(a._storage).sin_port        = htons(port);
            }
            return a;
        }

        int Address::family() const noexcept { return _storage.ss_family; }

        uint16_t Address::port() const noexcept
        {
            switch (family())
            {
                case AF_INET:
                    return ntohs(v4(_storage).sin_port);
                case AF_INET6:
                    return ntohs(v6(_storage).sin6_port);
                default:
                    return 0;
            }
        }

        void Address::set_port(uint16_t port) noexcept
        {
            if (family() == AF_INET)
                v4(_storage).sin_port = htons(port);
            else if (family() == AF_INET6)
                v6(_storage).sin6_port = htons(port);
        }

        bool Address::is_v4_mapped() const noexcept
        {
            return family() == AF_INET6 && std::memcmp(v6(_storage).sin6_addr.s6_addr, v4_mapped_prefix, 12) == 0;
        }

        Address Address::unmapped() const noexcept
        {
            if (!is_v4_mapped())
                return *this;
            Address a;
            v4(a._storage).sin_family = AF_INET;
            v4(a._storage).sin_port   = v6(_storage).sin6_port;
            std::memcpy(&v4(a._storage).sin_addr, v6(_storage).sin6_addr.s6_addr + 12, 4);
            return a;
        }

        bool Address::is_any() const noexcept
        {
            if (family() == AF_INET)
                return v4(_storage).sin_addr.s_addr == htonl(INADDR_ANY);
            if (family() == AF_INET6)
                return std::memcmp(&v6(_storage).sin6_addr, &in6addr_any, sizeof(in6_addr)) == 0;
            return false;
        }

        bool Address::is_loopback() const noexcept
        {
            const Address a = unmapped();
            if (a.family() == AF_INET)
                return (ntohl(v4(a._storage).sin_addr.s_addr) >> 24) == 127;
            if (a.family() == AF_INET6)
                return std::memcmp(&v6(a._storage).sin6_addr, &in6addr_loopback, sizeof(in6_addr)) == 0;
            return false;
        }

        bool Address::is_multicast() const noexcept
        {
            const Address a = unmapped();
            if (a.family() == AF_INET)
                return (ntohl(v4(a._storage).sin_addr.s_addr) >> 28) == 0xE;
            if (a.family() == AF_INET6)
                return v6(a._storage).sin6_addr.s6_addr[0] == 0xFF;
            return false;
        }

        std::string Address::host() const
        {
            const Address a = unmapped();
            char buf[INET6_ADDRSTRLEN] = {};
            if (a.family() == AF_INET)
                inet_ntop(AF_INET, &v4(a._storage).sin_addr, buf, sizeof buf);
            else if (a.family() == AF_INET6)
                inet_ntop(AF_INET6, &v6(a._storage).sin6_addr, buf, sizeof buf);
            return std::string(buf);
        }

        std::string Address::to_string() const
        {
            if (empty())
                return std::string();
            char port[8];
            const auto r = std::to_chars(port, port + sizeof port, this->port());
            const std::string h = host();
            const bool bracket  = unmapped().family() == AF_INET6;
            return (bracket ? "[" + h + "]" : h) + ":" + std::string(port, r.ptr);
        }

        socklen_t Address::length() const noexcept
        {
            switch (family())
            {
                case AF_INET:
                    return sizeof(sockaddr_in);
                case AF_INET6:
                    return sizeof(sockaddr_in6);
                default:
                    return 0;
            }
        }

        const unsigned char* Address::bytes() const noexcept
        {
            if (family() == AF_INET)
                return reinterpret_cast<const unsigned char*>(&v4(_storage).sin_addr);
            return v6(_storage).sin6_addr.s6_addr;
        }

        std::size_t Address::byte_count() const noexcept
        {
            switch (family())
            {
                case AF_INET:
                    return 4;
                case AF_INET6:
                    return 16;
                default:
                    return 0;
            }
        }

        bool Address::same_host(const Address& other) const noexcept
        {
            const Address a = unmapped();
            const Address b = other.unmapped();
            return a.family() == b.family() && a.byte_count() != 0
                && std::memcmp(a.bytes(), b.bytes(), a.byte_count()) == 0;
        }

        bool operator==(const Address& a, const Address& b) noexcept { return a.same_host(b) && a.port() == b.port(); }

    } // namespace vs
} // namespace Trick
