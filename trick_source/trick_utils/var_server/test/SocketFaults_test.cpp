// Socket failure paths, made with a hooked SystemInterface.

#include "NetTestUtil.hh"

#include "trick/vs/Connection.hh"
#include "trick/vs/Fd.hh"
#include "trick/vs/Listener.hh"

#include <gtest/gtest.h>

using namespace Trick::vs;
using namespace vs_test;

TEST(Fd, ClosesOnceThroughItsSystemInterface)
{
    HookedSystem sys;
    {
        Fd a(::dup(0), sys);
        ASSERT_TRUE(a.valid());
        Fd b(std::move(a));
        EXPECT_FALSE(a.valid());
        EXPECT_TRUE(b.valid());
        Fd c;
        c = std::move(b);
        EXPECT_EQ(sys.closes, 0);
    }
    EXPECT_EQ(sys.closes, 1);

    Fd d(::dup(0), sys);
    const int raw = d.release();
    EXPECT_FALSE(d.valid());
    ::close(raw);
    EXPECT_EQ(sys.closes, 1);
}

TEST(Fd, NonblockingAndCloexec)
{
    Fd fd(::socket(AF_INET, SOCK_STREAM, 0));
    ASSERT_TRUE(fd);
    ASSERT_TRUE(set_nonblocking(fd, true));
    EXPECT_TRUE(::fcntl(fd.get(), F_GETFL) & O_NONBLOCK);
    ASSERT_TRUE(set_nonblocking(fd, false));
    EXPECT_FALSE(::fcntl(fd.get(), F_GETFL) & O_NONBLOCK);
    ASSERT_TRUE(set_cloexec(fd));
    EXPECT_TRUE(::fcntl(fd.get(), F_GETFD) & FD_CLOEXEC);
    Fd bad(-1);
    EXPECT_FALSE(set_nonblocking(bad, true));
}

TEST(SocketFaults, SocketFailureIsAnErrorNotZero)
{
    // The old var_server_create_*_socket returned 0 on failure.
    HookedSystem sys;
    sys.on_socket = [](int, int, int) { return fail_with(EMFILE); };
    auto l        = Listener::open(sys, "127.0.0.1", 0);
    ASSERT_FALSE(l);
    EXPECT_NE(l.error().message.find("socket"), std::string::npos);
    EXPECT_FALSE(UdpConnection::open(sys, "127.0.0.1", 0));
    EXPECT_FALSE(MulticastConnection::open(sys, "224.1.2.3", "", 0));
}

TEST(SocketFaults, BindFailureClosesTheSocket)
{
    HookedSystem sys;
    sys.on_bind = [](int, const sockaddr*, socklen_t) { return fail_with(EADDRINUSE); };
    auto l      = Listener::open(sys, "127.0.0.1", 40000);
    ASSERT_FALSE(l);
    EXPECT_NE(l.error().message.find("127.0.0.1:40000"), std::string::npos);
    EXPECT_EQ(sys.closes, 1);
}

namespace
{
    /** A listener and one TcpConnection made with `sys`. */
    std::unique_ptr<TcpConnection> connected_pair(HookedSystem& sys, int& client, std::optional<Listener>& keep)
    {
        auto l = Listener::open(sys, "127.0.0.1", 0);
        if (!l)
            return nullptr;
        keep.emplace(std::move(l.value()));
        client = tcp_client(*Address::parse("127.0.0.1", keep->port()));
        std::unique_ptr<TcpConnection> server;
        eventually([&] {
            auto c = keep->accept_connection();
            if (c && c.value())
                server = std::move(c.value());
            return server != nullptr;
        });
        return server;
    }
} // namespace

TEST(SocketFaults, EagainKeepsTheBytesQueued)
{
    HookedSystem sys;
    int client = -1;
    std::optional<Listener> keep;
    auto server = connected_pair(sys, client, keep);
    ASSERT_TRUE(server);

    int calls   = 0;
    sys.on_send = [&](int fd, const void* b, std::size_t n, int f) -> ssize_t {
        ++calls;
        if (calls == 1)
            return ::send(fd, b, 3, f); // a short write
        if (calls == 2)
            return fail_with(EAGAIN);
        return ::send(fd, b, n, f);
    };
    server->send("0\thello\n");
    EXPECT_EQ(server->flush().status, FlushResult::Status::Pending);
    EXPECT_EQ(server->queue().size(), 5u);
    EXPECT_EQ(server->flush().status, FlushResult::Status::Done);
    EXPECT_EQ(recv_for(client, 500), "0\thello\n");
    ::close(client);
}

TEST(SocketFaults, InterruptedCallsAreRetried)
{
    HookedSystem sys;
    int client = -1;
    std::optional<Listener> keep;
    auto server = connected_pair(sys, client, keep);
    ASSERT_TRUE(server);

    int sends   = 0;
    sys.on_send = [&](int fd, const void* b, std::size_t n, int f) -> ssize_t {
        if (sends++ == 0)
            return fail_with(EINTR);
        return ::send(fd, b, n, f);
    };
    int recvs   = 0;
    sys.on_recv = [&](int fd, void* b, std::size_t n, int f) -> ssize_t {
        if (recvs++ == 0)
            return fail_with(EINTR);
        return ::recv(fd, b, n, f);
    };
    server->send("x\n");
    EXPECT_EQ(server->flush().status, FlushResult::Status::Done);
    send_all(client, "y\n");
    std::string batch;
    ReadResult r;
    eventually([&] {
        r = server->read(batch);
        return r.status == ReadResult::Status::Batch;
    });
    EXPECT_EQ(batch, "y\n");
    ::close(client);
}

TEST(SocketFaults, RecvErrorIsReported)
{
    HookedSystem sys;
    int client = -1;
    std::optional<Listener> keep;
    auto server = connected_pair(sys, client, keep);
    ASSERT_TRUE(server);
    sys.on_recv = [](int, void*, std::size_t, int) -> ssize_t { return fail_with(EIO); };
    std::string batch;
    auto r = server->read(batch);
    EXPECT_EQ(r.status, ReadResult::Status::Error);
    EXPECT_NE(r.note.find("recv"), std::string::npos);
    sys.on_recv = [](int, void*, std::size_t, int) -> ssize_t { return fail_with(ECONNRESET); };
    EXPECT_EQ(server->read(batch).status, ReadResult::Status::Closed);
    ::close(client);
}

TEST(SocketFaults, ClosedConnection)
{
    HookedSystem sys;
    int client = -1;
    std::optional<Listener> keep;
    auto server = connected_pair(sys, client, keep);
    ASSERT_TRUE(server);
    server->send("queued\n");
    server->close();
    EXPECT_FALSE(server->is_open());
    EXPECT_FALSE(server->wants_write()); // queued bytes are dropped
    std::string batch;
    EXPECT_EQ(server->read(batch).status, ReadResult::Status::Closed);
    EXPECT_TRUE(closed_by_peer(client, 1000));
    ::close(client);
}
