/*
PURPOSE: (The variable server's allowlist of client addresses.)

An entry is an IPv4 address ("10.1.2.3"), an IPv6 address ("fe80::1"), or
a CIDR block of either ("10.1.0.0/16", "fd00::/8"). A client is allowed
when any entry matches. An IPv4 client that reaches an IPv6 socket
(::ffff:10.1.2.3) is matched as IPv4.

The old check_ip() compared exact entries as strings and accepted CIDR
only for IPv4, with no range check on the prefix (a prefix over 32 shifted
by a negative count). Here every entry is parsed once; an entry that is not
an address or a valid block is reported and never matches.
*/

#ifndef TRICK_VS_ADDRESSFILTER_HH
#define TRICK_VS_ADDRESSFILTER_HH

#include "trick/vs/Address.hh"
#include "trick/vs/Expected.hh"

#include <string>
#include <string_view>
#include <vector>

namespace Trick
{
    namespace vs
    {

        class AddressFilter
        {
            public:
                /** One parsed entry. */
                struct Entry
                {
                        std::string text;
                        int family = AF_UNSPEC;
                        unsigned char bytes[16] = {};
                        unsigned prefix = 0; ///< bits that must match: 32 or 128 for one address
                };

                /** Parse one entry. */
                static Expected<Entry> parse(std::string_view text);

                /**
                 * Build a filter from the allowlist's strings. Entries that do not parse
                 * are left out; their errors are appended to `errors` if it is given.
                 */
                template <class Strings>
                static AddressFilter from(const Strings& entries, std::vector<std::string>* errors = nullptr)
                {
                    AddressFilter f;
                    for (const auto& s : entries)
                    {
                        auto e = f.add(s);
                        if (!e && errors != nullptr)
                            errors->push_back(e.error().message);
                    }
                    return f;
                }

                /** Add an entry. An entry that does not parse is not added. */
                Expected<void> add(std::string_view text);

                /** True if any entry matches the client's address. The port is ignored. */
                bool allows(const Address& client) const noexcept;

                const std::vector<Entry>& entries() const noexcept { return _entries; }

                bool empty() const noexcept { return _entries.empty(); }

            private:
                std::vector<Entry> _entries;
        };

    } // namespace vs
} // namespace Trick

#endif
