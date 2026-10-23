#include "trick/vs/AddressFilter.hh"

#include <charconv>
#include <cstring>

namespace Trick
{
    namespace vs
    {

        Expected<AddressFilter::Entry> AddressFilter::parse(std::string_view text)
        {
            Entry e;
            e.text = std::string(text);

            std::string_view host = text;
            std::string_view bits;
            const std::size_t slash = text.find('/');
            if (slash != std::string_view::npos)
            {
                host = text.substr(0, slash);
                bits = text.substr(slash + 1);
            }

            auto address = Address::parse(host);
            if (!address)
                return Error { "allowlist entry [" + e.text + "] is not an IPv4 or IPv6 address" };
            // ::ffff:a.b.c.d/n is the IPv4 block a.b.c.d/(n - 96).
            const bool mapped = address->is_v4_mapped();
            const Address a   = address->unmapped();
            e.family        = a.family();
            std::memcpy(e.bytes, a.bytes(), a.byte_count());
            const unsigned max_bits = static_cast<unsigned>(a.byte_count() * 8);

            if (slash == std::string_view::npos)
            {
                e.prefix = max_bits;
                return e;
            }
            const unsigned min_bits = mapped ? 96 : 0;
            const unsigned top_bits = mapped ? 128 : max_bits;
            unsigned prefix         = 0;
            const auto r            = std::from_chars(bits.data(), bits.data() + bits.size(), prefix);
            if (bits.empty() || r.ec != std::errc() || r.ptr != bits.data() + bits.size() || prefix < min_bits
                || prefix > top_bits)
                return Error { "allowlist entry [" + e.text + "] has a prefix length that is not " + std::to_string(min_bits)
                               + " to " + std::to_string(top_bits) };
            e.prefix = prefix - min_bits;
            return e;
        }

        Expected<void> AddressFilter::add(std::string_view text)
        {
            auto e = parse(text);
            if (!e)
                return e.error();
            _entries.push_back(std::move(e.value()));
            return {};
        }

        bool AddressFilter::allows(const Address& client) const noexcept
        {
            const Address a = client.unmapped();
            if (a.empty())
                return false;
            const unsigned char* bytes = a.bytes();
            for (const Entry& e : _entries)
            {
                if (e.family != a.family())
                    continue;
                const unsigned whole = e.prefix / 8;
                const unsigned rest  = e.prefix % 8;
                if (std::memcmp(e.bytes, bytes, whole) != 0)
                    continue;
                if (rest != 0)
                {
                    const unsigned char mask = static_cast<unsigned char>(0xFF << (8 - rest));
                    if ((e.bytes[whole] & mask) != (bytes[whole] & mask))
                        continue;
                }
                return true;
            }
            return false;
        }

    } // namespace vs
} // namespace Trick
