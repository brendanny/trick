// Real sockets on the loopback interface: Listener, TcpConnection,
// UdpConnection and MulticastConnection.

#include "NetTestUtil.hh"

#include "trick/vs/Connection.hh"
#include "trick/vs/Listener.hh"

#include <chrono>
#include <thread>

#include <gtest/gtest.h>

using namespace Trick::vs;
using namespace vs_test;

namespace
{
    /** A listener on 127.0.0.1 and one accepted client. */
    struct TcpPair
    {
            std::optional<Listener> listener;
            std::unique_ptr<TcpConnection> server;
            int client = -1;

            explicit TcpPair(const ConnectionOptions& options = {}, const char* host = "127.0.0.1")
            {
                auto l = Listener::open(system_interface(), host, 0);
                if (!l)
                {
                    ADD_FAILURE() << l.error().message;
                    return;
                }
                listener.emplace(std::move(l.value()));
                Address target = *Address::parse(std::string(host) == "::" ? "::1" : host, listener->port());
                client         = tcp_client(target);
                EXPECT_GE(client, 0);
                eventually([&] {
                    auto c = listener->accept_connection(options);
                    if (c && c.value())
                        server = std::move(c.value());
                    return server != nullptr;
                });
                EXPECT_TRUE(server);
            }

            ~TcpPair()
            {
                if (client >= 0)
                    ::close(client);
            }

            /** Read until a batch comes or `ms` pass. */
            ReadResult read_batch(std::string& batch, int ms = 2000)
            {
                ReadResult r;
                eventually(
                    [&] {
                        r = server->read(batch);
                        return r.status != ReadResult::Status::Nothing;
                    },
                    ms);
                return r;
            }
    };
} // namespace

// ---------------------------------------------------------------------------
// Listener and TCP
// ---------------------------------------------------------------------------

TEST(Listener, OpensOnAnOsChosenPort)
{
    auto l = Listener::open(system_interface(), "127.0.0.1", 0);
    ASSERT_TRUE(l) << l.error().message;
    EXPECT_GT(l.value().port(), 0);
    EXPECT_TRUE(l.value().address().is_loopback());
    EXPECT_EQ(l.value().hostname(), "127.0.0.1");
    // Nobody is waiting: accept returns nothing, without blocking.
    auto a = l.value().accept();
    ASSERT_TRUE(a);
    EXPECT_FALSE(a.value());
}

TEST(Listener, RequestedPortInUseIsAnError)
{
    auto a = Listener::open(system_interface(), "127.0.0.1", 0);
    ASSERT_TRUE(a);
    auto b = Listener::open(system_interface(), "127.0.0.1", a.value().port());
    ASSERT_FALSE(b);
    EXPECT_NE(b.error().message.find("bind"), std::string::npos);
}

TEST(Listener, DefaultNameBindsEveryInterface)
{
    auto l = Listener::open(system_interface(), "", 0);
    ASSERT_TRUE(l) << l.error().message;
    EXPECT_TRUE(l.value().address().is_any());
    EXPECT_EQ(l.value().hostname(), system_interface().hostname());
}

TEST(TcpConnection, ReadsBatchesAndPeer)
{
    TcpPair p;
    ASSERT_TRUE(p.server);
    EXPECT_TRUE(p.server->peer().is_loopback());
    EXPECT_EQ(p.server->kind(), ConnectionKind::Tcp);

    std::string batch;
    EXPECT_EQ(p.server->read(batch).status, ReadResult::Status::Nothing);
    send_all(p.client, "trick.var_pause()\r\ntrick.var_add(\"a\")\ntrick.var_");
    auto r = p.read_batch(batch);
    ASSERT_EQ(r.status, ReadResult::Status::Batch);
    EXPECT_EQ(batch, "trick.var_pause()\ntrick.var_add(\"a\")\n");
    send_all(p.client, "send()\n");
    r = p.read_batch(batch);
    ASSERT_EQ(r.status, ReadResult::Status::Batch);
    EXPECT_EQ(batch, "trick.var_send()\n");
}

TEST(TcpConnection, SendsQueuedMessages)
{
    TcpPair p;
    ASSERT_TRUE(p.server);
    ASSERT_TRUE(p.server->send("0\t1\n"));
    ASSERT_TRUE(p.server->send("0\t2\n"));
    EXPECT_TRUE(p.server->wants_write());
    EXPECT_EQ(p.server->flush().status, FlushResult::Status::Done);
    EXPECT_FALSE(p.server->wants_write());
    EXPECT_EQ(recv_for(p.client, 500), "0\t1\n0\t2\n");
}

TEST(TcpConnection, ClientCloseIsClosedAfterTheLastBatch)
{
    TcpPair p;
    ASSERT_TRUE(p.server);
    send_all(p.client, "trick.var_exit()\npartial");
    ::close(p.client);
    p.client = -1;
    std::string batch;
    auto r = p.read_batch(batch);
    ASSERT_EQ(r.status, ReadResult::Status::Batch);
    EXPECT_EQ(batch, "trick.var_exit()\n");
    r = p.read_batch(batch);
    EXPECT_EQ(r.status, ReadResult::Status::Closed);
    EXPECT_NE(r.note.find("7 bytes"), std::string::npos) << r.note;
}

TEST(TcpConnection, ThreeHundredKilobyteCommandWithNoNewline)
{
    // Phase 0 known defect: the old session stalled for good.
    TcpPair p;
    ASSERT_TRUE(p.server);
    std::thread sender([&] { send_all(p.client, "#" + std::string(300000, 'a')); });
    std::string batch;
    // Drain while the client sends, as the session runner would.
    ReadResult r;
    std::string notes;
    eventually(
        [&] {
            r = p.server->read(batch);
            notes += r.note;
            return p.server->pending_bytes() == 0 && !notes.empty();
        },
        3000);
    sender.join();
    send_all(p.client, "\ntrick.var_pause()\ntrick.var_send_once(\"x\")\n");
    eventually(
        [&] {
            r = p.server->read(batch);
            notes += r.note;
            return r.status == ReadResult::Status::Batch;
        },
        3000);
    ASSERT_EQ(r.status, ReadResult::Status::Batch);
    EXPECT_EQ(batch, "trick.var_pause()\ntrick.var_send_once(\"x\")\n");
    EXPECT_NE(notes.find("longer than 200000"), std::string::npos) << notes;
}

TEST(TcpConnection, SlowClientFillsTheQueueWithoutBlocking)
{
    // The old server dropped a client on the first EAGAIN. Here the bytes wait,
    // and only a full queue drops the client; the server never blocks.
    ConnectionOptions options;
    options.queue_capacity = 1 << 20;
    TcpPair p(options);
    ASSERT_TRUE(p.server);
    const std::string message(8192, 'v');

    const auto start = std::chrono::steady_clock::now();
    bool refused     = false;
    int queued       = 0;
    while (std::chrono::steady_clock::now() - start < std::chrono::seconds(10))
    {
        if (!p.server->send(message))
        {
            refused = true;
            break;
        }
        ++queued;
        auto f = p.server->flush();
        ASSERT_NE(f.status, FlushResult::Status::Error) << f.note;
    }
    const auto elapsed = std::chrono::steady_clock::now() - start;
    EXPECT_TRUE(refused);
    EXPECT_LT(elapsed, std::chrono::seconds(5));
    EXPECT_EQ(p.server->flush().status, FlushResult::Status::Pending);
    EXPECT_GT(p.server->queue().size(), options.queue_capacity - message.size());

    // When the client reads again, everything queued arrives, in order.
    std::size_t received = 0;
    std::thread reader([&] {
        char buf[65536];
        while (received < static_cast<std::size_t>(queued) * message.size())
        {
            if (!readable(p.client, 3000))
                break;
            const ssize_t n = ::recv(p.client, buf, sizeof buf, 0);
            if (n <= 0)
                break;
            received += static_cast<std::size_t>(n);
        }
    });
    eventually([&] { return p.server->flush().status == FlushResult::Status::Done; }, 5000);
    reader.join();
    EXPECT_EQ(received, static_cast<std::size_t>(queued) * message.size());
}

TEST(TcpConnection, SendToAClosedClientIsAnError)
{
    TcpPair p;
    ASSERT_TRUE(p.server);
    ::close(p.client);
    p.client = -1;
    FlushResult f;
    // The first sends may succeed into the kernel buffer; an error follows.
    eventually(
        [&] {
            p.server->send(std::string(65536, 'x'));
            f = p.server->flush();
            return f.status == FlushResult::Status::Error;
        },
        3000);
    EXPECT_EQ(f.status, FlushResult::Status::Error);
    EXPECT_NE(f.note.find("send"), std::string::npos);
    // EPIPE or ECONNRESET: the session logs it as information, not as an error.
    EXPECT_TRUE(f.client_closed) << f.note;
}

TEST(TcpConnection, Ipv6Loopback)
{
    if (!ipv6_loopback_available())
        GTEST_SKIP() << "no IPv6 loopback";
    TcpPair p({}, "::1");
    ASSERT_TRUE(p.server);
    EXPECT_EQ(p.listener->address().family(), AF_INET6);
    EXPECT_EQ(p.server->peer().host(), "::1");
    send_all(p.client, "x\n");
    std::string batch;
    ASSERT_EQ(p.read_batch(batch).status, ReadResult::Status::Batch);
}

TEST(TcpConnection, Ipv6AnyAlsoTakesIpv4Clients)
{
    if (!ipv6_loopback_available())
        GTEST_SKIP() << "no IPv6";
    auto l = Listener::open(system_interface(), "::", 0);
    ASSERT_TRUE(l) << l.error().message;
    const int client = tcp_client(*Address::parse("127.0.0.1", l.value().port()));
    ASSERT_GE(client, 0);
    std::unique_ptr<TcpConnection> server;
    eventually([&] {
        auto c = l.value().accept_connection();
        if (c && c.value())
            server = std::move(c.value());
        return server != nullptr;
    });
    ASSERT_TRUE(server);
    // The client is ::ffff:127.0.0.1 on the socket; it is reported as IPv4.
    EXPECT_EQ(server->peer().family(), AF_INET);
    EXPECT_EQ(server->peer().host(), "127.0.0.1");
    ::close(client);
}

// ---------------------------------------------------------------------------
// UDP
// ---------------------------------------------------------------------------

namespace
{
    void send_datagram(int fd, const Address& to, const std::string& data)
    {
        ::sendto(fd, data.data(), data.size(), 0, to.data(), to.length());
    }

    ReadResult read_until_batch(Connection& c, std::string& batch, std::string* notes = nullptr, int ms = 2000)
    {
        ReadResult r;
        eventually(
            [&] {
                r = c.read(batch);
                if (notes)
                    *notes += r.note;
                return r.status == ReadResult::Status::Batch;
            },
            ms);
        return r;
    }
} // namespace

TEST(UdpConnection, OneDatagramIsOneBatchAndRepliesGoToTheSender)
{
    auto u = UdpConnection::open(system_interface(), "127.0.0.1", 0);
    ASSERT_TRUE(u) << u.error().message;
    UdpConnection& server = *u.value();
    EXPECT_EQ(server.kind(), ConnectionKind::Udp);
    // Decision 12: "127.0.0.1" binds loopback only.
    EXPECT_TRUE(server.local().is_loopback());
    const Address server_address = *Address::parse("127.0.0.1", server.local().port());

    Address client_address;
    const int client = udp_socket(&client_address);
    send_datagram(client, server_address, "trick.var_add(\"a\")\r\ntrick.var_send()\n");
    std::string batch;
    ASSERT_EQ(read_until_batch(server, batch).status, ReadResult::Status::Batch);
    EXPECT_EQ(batch, "trick.var_add(\"a\")\ntrick.var_send()\n");
    EXPECT_EQ(server.peer(), client_address);

    ASSERT_TRUE(server.send("0\t1\n"));
    ASSERT_TRUE(server.send("0\t2\n"));
    EXPECT_EQ(server.flush().status, FlushResult::Status::Done);
    char buf[64];
    ASSERT_TRUE(readable(client, 1000));
    EXPECT_EQ(std::string(buf, static_cast<std::size_t>(::recv(client, buf, sizeof buf, 0))), "0\t1\n");
    ASSERT_TRUE(readable(client, 1000));
    EXPECT_EQ(std::string(buf, static_cast<std::size_t>(::recv(client, buf, sizeof buf, 0))), "0\t2\n");
    ::close(client);
}

TEST(UdpConnection, PartialDatagrams)
{
    auto u = UdpConnection::open(system_interface(), "127.0.0.1", 0);
    ASSERT_TRUE(u);
    UdpConnection& server = *u.value();
    const Address server_address = *Address::parse("127.0.0.1", server.local().port());
    const int client             = udp_socket();

    // No newline: dropped, with a note. The old server never consumed it and stalled.
    send_datagram(client, server_address, "trick.var_send()");
    send_datagram(client, server_address, "a\nb\nleft over");
    std::string batch, notes;
    ASSERT_EQ(read_until_batch(server, batch, &notes).status, ReadResult::Status::Batch);
    EXPECT_EQ(batch, "a\nb\n");
    EXPECT_NE(notes.find("no newline"), std::string::npos) << notes;
    EXPECT_NE(notes.find("9 bytes after the last newline"), std::string::npos) << notes;
    ::close(client);
}

TEST(UdpConnection, AllowlistIsCheckedAgainstEachSender)
{
    // The old UDP session checked an address that no datagram had set yet.
    auto u = UdpConnection::open(system_interface(), "127.0.0.1", 0);
    ASSERT_TRUE(u);
    UdpConnection& server = *u.value();
    Address allowed_client;
    const int good = udp_socket(&allowed_client);
    const int bad  = udp_socket();
    server.set_sender_filter([&](const Address& a) { return a == allowed_client; });
    const Address server_address = *Address::parse("127.0.0.1", server.local().port());

    send_datagram(bad, server_address, "print('no')\n");
    send_datagram(good, server_address, "print('yes')\n");
    std::string batch, notes;
    ASSERT_EQ(read_until_batch(server, batch, &notes).status, ReadResult::Status::Batch);
    EXPECT_EQ(batch, "print('yes')\n");
    EXPECT_NE(notes.find("ILLEGAL IP"), std::string::npos);
    EXPECT_EQ(server.peer(), allowed_client); // replies never go to the refused sender
    ::close(good);
    ::close(bad);
}

TEST(UdpConnection, NoClientYetDropsReplies)
{
    auto u = UdpConnection::open(system_interface(), "127.0.0.1", 0);
    ASSERT_TRUE(u);
    u.value()->send("0\t1\n");
    auto f = u.value()->flush();
    EXPECT_EQ(f.status, FlushResult::Status::Done);
    EXPECT_NE(f.note.find("no client"), std::string::npos);
    EXPECT_FALSE(u.value()->wants_write());
}

// ---------------------------------------------------------------------------
// Multicast
// ---------------------------------------------------------------------------

namespace
{
    /** A socket that receives `group`:port, as the SIM_test_varserv client does. -1 if the host cannot. */
    int group_listener(const char* group, uint16_t port)
    {
        const int fd = ::socket(AF_INET, SOCK_DGRAM, 0);
        const int one = 1;
        ::setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
#ifdef SO_REUSEPORT
        ::setsockopt(fd, SOL_SOCKET, SO_REUSEPORT, &one, sizeof one);
#endif
        Address a = *Address::parse(group, port);
        ip_mreq m {};
        inet_pton(AF_INET, group, &m.imr_multiaddr);
        m.imr_interface.s_addr = htonl(INADDR_ANY);
        if (::bind(fd, a.data(), a.length()) != 0
            || ::setsockopt(fd, IPPROTO_IP, IP_ADD_MEMBERSHIP, &m, sizeof m) != 0)
        {
            ::close(fd);
            return -1;
        }
        return fd;
    }
} // namespace

namespace
{
    void multicast_round_trip(const char* group, const char* source)
    {
    auto m            = MulticastConnection::open(system_interface(), group, source, 0);
    ASSERT_TRUE(m) << m.error().message;
    MulticastConnection& server = *m.value();
    EXPECT_EQ(server.kind(), ConnectionKind::Multicast);
    EXPECT_EQ(server.peer(), *Address::parse(group, server.local().port()));

    const int listener = group_listener(group, server.local().port());
    if (listener < 0)
        GTEST_SKIP() << "cannot join a multicast group here";
    const int client = udp_socket();
    send_datagram(client, *Address::parse("127.0.0.1", server.local().port()), "trick.var_send()\n");
    std::string batch;
    ASSERT_EQ(read_until_batch(server, batch).status, ReadResult::Status::Batch);
    EXPECT_EQ(batch, "trick.var_send()\n");

    // A reply that looks like a command: the old server ran its own output.
    ASSERT_TRUE(server.send("trick.var_exit()\n"));
    EXPECT_EQ(server.flush().status, FlushResult::Status::Done);
    if (!readable(listener, 1000))
    {
        ::close(listener);
        ::close(client);
        GTEST_SKIP() << "multicast loopback is off here";
    }
    char buf[64];
    EXPECT_EQ(std::string(buf, static_cast<std::size_t>(::recv(listener, buf, sizeof buf, 0))), "trick.var_exit()\n");
    // The server must not read its own datagram back.
    std::this_thread::sleep_for(std::chrono::milliseconds(200));
    EXPECT_EQ(server.read(batch).status, ReadResult::Status::Nothing);
    ::close(listener);
    ::close(client);
}
} // namespace

TEST(MulticastConnection, BoundToLoopback)
{
    // Decision 12: commands only from this host; replies still reach the group.
    multicast_round_trip("224.10.10.77", "127.0.0.1");
}

TEST(MulticastConnection, BoundToEveryInterface) { multicast_round_trip("224.10.10.78", ""); }

TEST(MulticastConnection, GroupMustBeMulticast)
{
    EXPECT_FALSE(MulticastConnection::open(system_interface(), "10.0.0.1", "", 0));
    EXPECT_FALSE(MulticastConnection::open(system_interface(), "", "", 0));
    EXPECT_FALSE(MulticastConnection::open(system_interface(), "not-an-address", "", 0));
}
