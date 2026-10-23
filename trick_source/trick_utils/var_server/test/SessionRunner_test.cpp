// Phase 5: SessionRunner on loopback sockets. A runner owns its connection,
// runs commands when they arrive, sends on its cycle, sends what the main
// thread copied as soon as it is woken, and ends on var_exit, on a closed
// connection or on stop().

#include "NetTestUtil.hh"
#include "SessionHarness.hh"

#include "trick/vs/FixedReply.hh"
#include "trick/vs/Listener.hh"
#include "trick/vs/SessionRunner.hh"

#include <atomic>
#include <chrono>
#include <cstdio>
#include <memory>
#include <string>
#include <thread>

#include <gtest/gtest.h>

using namespace vs_test;
using namespace std::chrono_literals;

namespace
{
    class CountingHooks : public RunnerHooks
    {
        public:
            std::atomic<int> runs { 0 };
            std::atomic<int> started_count { 0 };
            std::atomic<int> finished_count { 0 };

            void run(Session&, const std::function<void()>& work) override
            {
                ++runs;
                work();
            }
            void started(Session&) override { ++started_count; }
            void finished(Session&) override { ++finished_count; }
    };

    /** A runner on an accepted loopback TCP client, with the client's socket. */
    struct TcpRig
    {
            FakeResolver model;
            FakeUnitConverter units;
            FakeClock clock;
            FakeHost host;
            CountingHooks hooks;
            std::shared_ptr<SessionRunner> runner;
            int client = -1;

            explicit TcpRig(bool real_time = false, std::size_t queue = WriteQueue::default_capacity)
            {
                model.set_scalar("a.x", WireType::Integer, 7, "1");
                clock.tics_per_second = 1000;
                clock.is_real_time    = real_time;
                auto listener         = Listener::open(system_interface(), "127.0.0.1", 0);
                EXPECT_TRUE(listener);
                client = tcp_client(listener.value().address());
                EXPECT_GE(client, 0);
                ConnectionOptions options;
                options.queue_capacity = queue;
                std::unique_ptr<TcpConnection> conn;
                EXPECT_TRUE(eventually([&] {
                    auto c = listener.value().accept_connection(options);
                    if (c && c.value())
                        conn = std::move(c.value());
                    return conn != nullptr;
                }));
                auto made = SessionRunner::create(
                    std::move(conn),
                    [this](SessionOutput& out) {
                        SessionConfig config;
                        return std::make_shared<Session>(host, model, units, clock, clock, out, config);
                    },
                    hooks);
                EXPECT_TRUE(made);
                runner = made.value();
                runner->start();
            }

            ~TcpRig()
            {
                runner->stop();
                EXPECT_TRUE(runner->wait_until(std::chrono::steady_clock::now() + 5s));
                runner->join();
                if (client >= 0)
                    ::close(client);
            }

            void send(const std::string& text) { send_all(client, text); }
    };

    std::string recv_until(int fd, const std::string& want, int ms = 3000)
    {
        std::string got;
        eventually(
            [&] {
                got += recv_for(fd, 20);
                return got.size() >= want.size();
            },
            ms);
        return got;
    }

} // namespace

TEST(SessionRunner, CommandsGetRepliesAtOnce)
{
    TcpRig rig;
    rig.send("trick.var_pause()\ntrick.var_add(\"a.x\")\ntrick.var_send()\n");
    EXPECT_EQ(recv_until(rig.client, "0\t7\n"), "0\t7\n");
    EXPECT_GE(rig.hooks.started_count.load(), 1);
    EXPECT_GE(rig.hooks.runs.load(), 1);
}

TEST(SessionRunner, SendsOnItsCycle)
{
    TcpRig rig;
    rig.send("trick.var_cycle(0.02)\ntrick.var_add(\"a.x\")\n");
    std::string got;
    EXPECT_TRUE(eventually(
        [&] {
            got += recv_for(rig.client, 20);
            return got.size() >= 5 * 4;
        },
        3000));
    EXPECT_EQ(got.substr(0, 8), "0\t7\n0\t7\n");
}

TEST(SessionRunner, VarExitClosesTheConnection)
{
    TcpRig rig;
    rig.send("trick.var_exit()\n");
    EXPECT_TRUE(closed_by_peer(rig.client, 3000));
    EXPECT_TRUE(rig.runner->wait_until(std::chrono::steady_clock::now() + 3s));
    EXPECT_EQ(rig.hooks.finished_count.load(), 1);
}

TEST(SessionRunner, AClosedClientEndsTheRunner)
{
    TcpRig rig;
    ::close(rig.client);
    rig.client = -1;
    EXPECT_TRUE(rig.runner->wait_until(std::chrono::steady_clock::now() + 3s));
}

TEST(SessionRunner, StopEndsAnIdleRunner)
{
    TcpRig rig;
    rig.send("trick.var_cycle(100.0)\n");
    std::this_thread::sleep_for(20ms);
    const auto t0 = std::chrono::steady_clock::now();
    rig.runner->stop();
    EXPECT_TRUE(rig.runner->wait_until(t0 + 2s));
    EXPECT_LT(std::chrono::steady_clock::now() - t0, 1s);
}

TEST(SessionRunner, TheMainThreadWakesItToSendWhatItCopied)
{
    TcpRig rig(true);
    rig.send("trick.var_cycle(60.0)\ntrick.var_add(\"a.x\")\ntrick.var_sync(2)\ntrick.var_send_list_size()\n");
    EXPECT_EQ(recv_until(rig.client, "3\t1\n"), "3\t1\n"); // the commands ran
    Session& s = *rig.runner->session();
    // This thread is the main thread now.
    s.main_refresh(0, 0);
    const auto t0 = std::chrono::steady_clock::now();
    s.main_copy_scheduled(s.next_tics());
    EXPECT_EQ(recv_until(rig.client, "0\t7\n"), "0\t7\n");
    EXPECT_LT(std::chrono::steady_clock::now() - t0, 2s); // long before the 60 s cycle
}

TEST(SessionRunner, ALargeFileArrivesWholeThroughASmallQueue)
{
    std::string contents(3 * 1024 * 1024, '\0');
    for (std::size_t i = 0; i < contents.size(); ++i)
        contents[i] = static_cast<char>('a' + i % 26);
    char name[] = "/tmp/vs_runner_file_XXXXXX";
    const int fd = ::mkstemp(name);
    ASSERT_GE(fd, 0);
    ASSERT_EQ(::write(fd, contents.data(), contents.size()), static_cast<ssize_t>(contents.size()));
    ::close(fd);

    TcpRig rig(false, 128 * 1024);
    rig.send(std::string("trick.var_pause()\ntrick.send_file(\"") + name + "\")\ntrick.var_exists(\"a.x\")\n");
    const std::string want = file_header(contents.size()) + contents + var_exists_reply(true, false);
    const std::string got  = recv_until(rig.client, want, 10000);
    EXPECT_EQ(got.size(), want.size());
    EXPECT_TRUE(got == want);
    EXPECT_FALSE(rig.runner->session()->exiting());
    std::remove(name);
}

TEST(SessionRunner, UdpSessionRepliesToTheSender)
{
    FakeResolver model;
    model.set_scalar("a.x", WireType::Integer, 7, "1");
    FakeUnitConverter units;
    FakeClock clock;
    FakeHost host;
    RunnerHooks hooks;
    auto conn = UdpConnection::open(system_interface(), "127.0.0.1", 0);
    ASSERT_TRUE(conn);
    const Address server = conn.value()->local();
    auto made            = SessionRunner::create(
        std::move(conn.value()),
        [&](SessionOutput& out) {
            return std::make_shared<Session>(host, model, units, clock, clock, out, SessionConfig {});
        },
        hooks);
    ASSERT_TRUE(made);
    auto runner = made.value();
    runner->start();

    Address me;
    const int client = udp_socket(&me);
    const std::string cmd = "trick.var_pause()\ntrick.var_add(\"a.x\")\ntrick.var_send()\n";
    ::sendto(client, cmd.data(), cmd.size(), 0, server.data(), server.length());
    EXPECT_EQ(recv_until(client, "0\t7\n"), "0\t7\n");

    runner->stop();
    EXPECT_TRUE(runner->wait_until(std::chrono::steady_clock::now() + 3s));
    runner->join();
    ::close(client);
}
