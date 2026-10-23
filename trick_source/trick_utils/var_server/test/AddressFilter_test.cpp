#include "NetTestUtil.hh"

#include "trick/vs/AddressFilter.hh"
#include "trick/vs/Endpoint.hh"

#include <set>

#include <gtest/gtest.h>

using namespace Trick::vs;
using vs_test::HookedSystem;

namespace
{
    Address addr(const char* text) { return *Address::parse(text); }
} // namespace

// ---------------------------------------------------------------------------
// Address
// ---------------------------------------------------------------------------

TEST(Address, ParsesNumericAddressesOnly)
{
    auto v4 = Address::parse("10.1.2.3", 40000);
    ASSERT_TRUE(v4);
    EXPECT_EQ(v4->family(), AF_INET);
    EXPECT_EQ(v4->port(), 40000);
    EXPECT_EQ(v4->host(), "10.1.2.3");
    EXPECT_EQ(v4->to_string(), "10.1.2.3:40000");

    auto v6 = Address::parse("[fe80::1]", 7);
    ASSERT_TRUE(v6);
    EXPECT_EQ(v6->family(), AF_INET6);
    EXPECT_EQ(v6->to_string(), "[fe80::1]:7");

    EXPECT_FALSE(Address::parse("localhost"));
    EXPECT_FALSE(Address::parse("10.1.2"));
    EXPECT_FALSE(Address::parse(""));
}

TEST(Address, MappedIpv4)
{
    const Address m = addr("::ffff:192.168.0.9");
    EXPECT_TRUE(m.is_v4_mapped());
    EXPECT_EQ(m.unmapped().family(), AF_INET);
    EXPECT_EQ(m.host(), "192.168.0.9"); // prints as IPv4
    EXPECT_TRUE(m.same_host(addr("192.168.0.9")));
    EXPECT_TRUE(addr("::ffff:127.0.0.1").is_loopback());
}

TEST(Address, Classes)
{
    EXPECT_TRUE(addr("127.0.0.5").is_loopback());
    EXPECT_TRUE(addr("::1").is_loopback());
    EXPECT_FALSE(addr("10.0.0.1").is_loopback());
    EXPECT_TRUE(addr("224.3.14.15").is_multicast());
    EXPECT_TRUE(addr("239.3.14.15").is_multicast());
    EXPECT_TRUE(addr("ff02::1").is_multicast());
    EXPECT_FALSE(addr("223.0.0.1").is_multicast());
    EXPECT_TRUE(Address::any(AF_INET, 0).is_any());
    EXPECT_TRUE(Address::any(AF_INET6, 0).is_any());
    EXPECT_TRUE(Address().empty());
}

TEST(Address, Equality)
{
    EXPECT_EQ(*Address::parse("10.0.0.1", 5), *Address::parse("10.0.0.1", 5));
    EXPECT_NE(*Address::parse("10.0.0.1", 5), *Address::parse("10.0.0.1", 6));
    EXPECT_TRUE(Address::parse("10.0.0.1", 5)->same_host(*Address::parse("10.0.0.1", 6)));
    EXPECT_FALSE(Address().same_host(Address()));
}

// ---------------------------------------------------------------------------
// AddressFilter
// ---------------------------------------------------------------------------

TEST(AddressFilter, EmptyAllowsNobody)
{
    AddressFilter f;
    EXPECT_FALSE(f.allows(addr("127.0.0.1")));
}

TEST(AddressFilter, ExactEntries)
{
    AddressFilter f;
    ASSERT_TRUE(f.add("10.1.2.3"));
    ASSERT_TRUE(f.add("fe80::1"));
    EXPECT_TRUE(f.allows(*Address::parse("10.1.2.3", 51000))); // the port is ignored
    EXPECT_FALSE(f.allows(addr("10.1.2.4")));
    EXPECT_TRUE(f.allows(addr("fe80::1")));
    EXPECT_TRUE(f.allows(addr("fe80:0:0:0:0:0:0:1"))); // the same address, written longer
    EXPECT_FALSE(f.allows(addr("fe80::2")));
    EXPECT_FALSE(f.allows(Address()));
}

TEST(AddressFilter, MappedClientsMatchIpv4Entries)
{
    // An IPv4 client of a "::" socket arrives as ::ffff:a.b.c.d.
    AddressFilter f;
    ASSERT_TRUE(f.add("127.0.0.1"));
    EXPECT_TRUE(f.allows(addr("::ffff:127.0.0.1")));
    AddressFilter g;
    ASSERT_TRUE(g.add("::ffff:10.0.0.0/104"));
    EXPECT_TRUE(g.allows(addr("10.9.8.7")));
}

TEST(AddressFilter, Ipv4Blocks)
{
    AddressFilter f;
    ASSERT_TRUE(f.add("192.168.0.0/16"));
    EXPECT_TRUE(f.allows(addr("192.168.200.1")));
    EXPECT_FALSE(f.allows(addr("192.169.0.1")));

    AddressFilter odd;
    ASSERT_TRUE(odd.add("10.0.0.64/26")); // 10.0.0.64 - 10.0.0.127
    EXPECT_FALSE(odd.allows(addr("10.0.0.63")));
    EXPECT_TRUE(odd.allows(addr("10.0.0.64")));
    EXPECT_TRUE(odd.allows(addr("10.0.0.127")));
    EXPECT_FALSE(odd.allows(addr("10.0.0.128")));

    AddressFilter all;
    ASSERT_TRUE(all.add("0.0.0.0/0"));
    EXPECT_TRUE(all.allows(addr("8.8.8.8")));
    EXPECT_FALSE(all.allows(addr("::1"))); // an IPv4 block never matches IPv6

    AddressFilter one;
    ASSERT_TRUE(one.add("10.0.0.5/32"));
    EXPECT_TRUE(one.allows(addr("10.0.0.5")));
    EXPECT_FALSE(one.allows(addr("10.0.0.4")));
}

TEST(AddressFilter, Ipv6Blocks)
{
    AddressFilter f;
    ASSERT_TRUE(f.add("fd00::/8"));
    EXPECT_TRUE(f.allows(addr("fd12:3456::1")));
    EXPECT_FALSE(f.allows(addr("fe80::1")));
    AddressFilter g;
    ASSERT_TRUE(g.add("2001:db8:abcd:12::/63"));
    EXPECT_TRUE(g.allows(addr("2001:db8:abcd:13::9")));
    EXPECT_FALSE(g.allows(addr("2001:db8:abcd:14::9")));
    AddressFilter h;
    ASSERT_TRUE(h.add("::1/128"));
    EXPECT_TRUE(h.allows(addr("::1")));
}

TEST(AddressFilter, BadEntriesAreReportedAndNeverMatch)
{
    // The old check_ip() shifted by a negative count for "/33" and threw for "/x".
    for (const char* bad : { "localhost", "10.0.0.0/33", "::ffff:10.0.0.0/95", "10.0.0.0/x", "10.0.0.0/", "::/129", "10.0.0/8", "10.0.0.0/-1",
                             "10.0.0.0/8/8", "" })
    {
        AddressFilter f;
        auto r = f.add(bad);
        EXPECT_FALSE(r) << bad;
        EXPECT_TRUE(f.empty()) << bad;
    }
    std::vector<std::string> errors;
    const std::set<std::string> list = { "127.0.0.1", "not an address", "10.0.0.0/40" };
    AddressFilter f = AddressFilter::from(list, &errors);
    EXPECT_EQ(f.entries().size(), 1u);
    EXPECT_EQ(errors.size(), 2u);
    EXPECT_TRUE(f.allows(addr("127.0.0.1")));
}

// ---------------------------------------------------------------------------
// Bind address rules (the old TCPClientListener / UDPConnection rules)
// ---------------------------------------------------------------------------

TEST(Endpoint, EveryInterfaceForTheDefaultNames)
{
    HookedSystem sys;
    for (const char* name : { "", "localhost", "testhost" })
    {
        auto t = resolve_bind_address(sys, name, 40000, SocketKind::Tcp);
        ASSERT_TRUE(t) << name;
        EXPECT_TRUE(t.value().address.is_any()) << name;
        EXPECT_EQ(t.value().address.family(), AF_INET);
        EXPECT_EQ(t.value().address.port(), 40000);
        EXPECT_EQ(t.value().hostname, "testhost");
    }
}

TEST(Endpoint, LoopbackBindsLoopbackForEveryKind)
{
    // Decision 12: the old UDP code bound every interface for "127.0.0.1".
    HookedSystem sys;
    for (SocketKind kind : { SocketKind::Tcp, SocketKind::Udp })
    {
        auto t = resolve_bind_address(sys, "127.0.0.1", 0, kind);
        ASSERT_TRUE(t);
        EXPECT_TRUE(t.value().address.is_loopback());
        EXPECT_FALSE(t.value().address.is_any());
        EXPECT_EQ(t.value().hostname, "127.0.0.1");
    }
    // "localhost" keeps the old rule: every interface.
    auto local = resolve_bind_address(sys, "localhost", 0, SocketKind::Udp);
    ASSERT_TRUE(local);
    EXPECT_TRUE(local.value().address.is_any());
}

TEST(Endpoint, NumericAddresses)
{
    HookedSystem sys;
    auto v4 = resolve_bind_address(sys, "10.1.2.3", 5, SocketKind::Tcp);
    ASSERT_TRUE(v4);
    EXPECT_EQ(v4.value().address.host(), "10.1.2.3");
    EXPECT_EQ(v4.value().hostname, "10.1.2.3");
    auto any4 = resolve_bind_address(sys, "0.0.0.0", 5, SocketKind::Tcp);
    ASSERT_TRUE(any4);
    EXPECT_EQ(any4.value().hostname, "0.0.0.0"); // as the old server reported it

    // Rewrite decision 6: an IPv6 source address turns IPv6 on.
    auto any6 = resolve_bind_address(sys, "::", 5, SocketKind::Tcp);
    ASSERT_TRUE(any6);
    EXPECT_EQ(any6.value().address.family(), AF_INET6);
    EXPECT_TRUE(any6.value().address.is_any());
    EXPECT_EQ(any6.value().hostname, "testhost");
    auto lo6 = resolve_bind_address(sys, "::1", 5, SocketKind::Tcp);
    ASSERT_TRUE(lo6);
    EXPECT_EQ(lo6.value().hostname, "::1");
}

TEST(Endpoint, NamesAreLookedUp)
{
    HookedSystem sys;
    sys.host_name = "not-this-name";
    auto t        = resolve_bind_address(sys, "localhost.", 9, SocketKind::Tcp);
    // "localhost." is not one of the special names, so it is looked up.
    if (t)
    {
        EXPECT_TRUE(t.value().address.is_loopback());
        EXPECT_EQ(t.value().hostname, "localhost.");
    }
    EXPECT_FALSE(resolve_bind_address(sys, "no-such-host.invalid", 9, SocketKind::Tcp));
}
