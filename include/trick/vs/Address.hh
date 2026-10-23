/*
PURPOSE: (An IPv4 or IPv6 socket address.)
*/

#ifndef TRICK_VS_ADDRESS_HH
#define TRICK_VS_ADDRESS_HH

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>

#include <netinet/in.h>
#include <sys/socket.h>

namespace Trick
{
    namespace vs
    {

        class Address
        {
            public:
                Address() noexcept;

                /** From a sockaddr of `length` bytes. An unknown family gives an empty Address. */
                Address(const sockaddr* address, socklen_t length) noexcept;

                /** A numeric IPv4 or IPv6 address ("10.0.0.1", "::1"), with a port. No name lookup. */
                static std::optional<Address> parse(std::string_view text, uint16_t port = 0);

                /** 0.0.0.0 or ::, with a port. */
                static Address any(int family, uint16_t port) noexcept;

                int family() const noexcept;

                bool empty() const noexcept { return family() == AF_UNSPEC; }

                uint16_t port() const noexcept;

                void set_port(uint16_t port) noexcept;

                /** True for an IPv6 address of the form ::ffff:a.b.c.d. */
                bool is_v4_mapped() const noexcept;

                /** The address with ::ffff:a.b.c.d turned into a.b.c.d. Others are unchanged. */
                Address unmapped() const noexcept;

                bool is_any() const noexcept;

                bool is_loopback() const noexcept;

                bool is_multicast() const noexcept;

                /** The address without the port: "10.0.0.1", "::1". A mapped address prints as IPv4. */
                std::string host() const;

                /** "10.0.0.1:40000" or "[::1]:40000". */
                std::string to_string() const;

                const sockaddr* data() const noexcept { return reinterpret_cast<const sockaddr*>(&_storage); }

                sockaddr* data() noexcept { return reinterpret_cast<sockaddr*>(&_storage); }

                socklen_t length() const noexcept;

                static constexpr socklen_t capacity() noexcept { return sizeof(sockaddr_storage); }

                /** The 4 (IPv4) or 16 (IPv6) address bytes, in network order. */
                const unsigned char* bytes() const noexcept;

                std::size_t byte_count() const noexcept;

                /** Same family, address and port. */
                friend bool operator==(const Address& a, const Address& b) noexcept;

                friend bool operator!=(const Address& a, const Address& b) noexcept { return !(a == b); }

                /** Same family and address; the ports may differ. */
                bool same_host(const Address& other) const noexcept;

            private:
                sockaddr_storage _storage;
        };

    } // namespace vs
} // namespace Trick

#endif
