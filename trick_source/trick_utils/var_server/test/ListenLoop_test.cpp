// Poller, Beacon and ListenLoop, on real loopback sockets and with a hooked
// SystemInterface for the failure paths.

#include "NetTestUtil.hh"

#include "trick/vs/Beacon.hh"
#include "trick/vs/ListenLoop.hh"
#include "trick/vs/Poller.hh"

#include <atomic>
#include <fstream>
#include <mutex>
#include <sstream>
#include <thread>

#include <gtest/gtest.h>

#ifndef VS_CONFORMANCE_DIR
#error "VS_CONFORMANCE_DIR must name test/SIM_vs_conformance"
#endif

using namespace Trick::vs;
using namespace vs_test;

// ---------------------------------------------------------------------------
// Poller
// ---------------------------------------------------------------------------

TEST(Poller, TimesOut)
{
    auto p = Poller::create();
    ASSERT_TRUE(p);
    std::vector<pollfd> none;
    const auto start = std::chrono::steady_clock::now();
    auto r           = p.value().wait(none, 50);
    ASSERT_TRUE(r);
    EXPECT_FALSE(r.value());
    EXPECT_GE(std::chrono::steady_clock::now() - start, std::chrono::milliseconds(40));
}

TEST(Poller, WakeFromAnotherThread)
{
    auto p = Poller::create();
    ASSERT_TRUE(p);
    Poller& poller = p.value();
    std::thread t([&] {
        std::this_thread::sleep_for(std::chrono::milliseconds(30));
        poller.wake();
    });
    std::vector<pollfd> none;
    auto r = poller.wait(none, 5000);
    t.join();
    ASSERT_TRUE(r);
    EXPECT_TRUE(r.value());
    // The wake was consumed.
    r = poller.wait(none, 0);
    ASSERT_TRUE(r);
    EXPECT_FALSE(r.value());
}

TEST(Poller, ManyWakesNeverBlock)
{
    auto p = Poller::create();
    ASSERT_TRUE(p);
    for (int i = 0; i < 100000; ++i) // more than a pipe holds
        p.value().wake();
    std::vector<pollfd> none;
    EXPECT_TRUE(p.value().wait(none, 0).value());
}

TEST(Poller, ReportsReadySockets)
{
    auto p = Poller::create();
    ASSERT_TRUE(p);
    int fds[2];
    ASSERT_EQ(::socketpair(AF_UNIX, SOCK_STREAM, 0, fds), 0);
    std::vector<pollfd> items = { { fds[0], POLLIN, 0 } };
    EXPECT_FALSE(p.value().wait(items, 0).value());
    EXPECT_EQ(items[0].revents, 0);
    ASSERT_EQ(::write(fds[1], "x", 1), 1);
    EXPECT_FALSE(p.value().wait(items, 1000).value());
    EXPECT_TRUE(items[0].revents & POLLIN);
    ::close(fds[0]);
    ::close(fds[1]);
}

TEST(Poller, InterruptedWaitIsNotAnError)
{
    HookedSystem sys;
    auto p = Poller::create(sys);
    ASSERT_TRUE(p);
    sys.on_poll = [](pollfd*, nfds_t, int) { return fail_with(EINTR); };
    std::vector<pollfd> none;
    auto r = p.value().wait(none, 1000);
    ASSERT_TRUE(r);
    EXPECT_FALSE(r.value());
    sys.on_poll = [](pollfd*, nfds_t, int) { return fail_with(ENOMEM); };
    EXPECT_FALSE(p.value().wait(none, 1000));
}

TEST(Poller, PipeFailureIsReported)
{
    HookedSystem sys;
    sys.on_pipe = [](int*) { return fail_with(EMFILE); };
    auto p      = Poller::create(sys);
    ASSERT_FALSE(p);
    EXPECT_NE(p.error().message.find("pipe"), std::string::npos);
}

// ---------------------------------------------------------------------------
// Beacon
// ---------------------------------------------------------------------------

namespace
{
    std::vector<std::string> split_tabs(const std::string& s)
    {
        std::vector<std::string> out;
        std::size_t start = 0;
        while (true)
        {
            const std::size_t tab = s.find('\t', start);
            out.push_back(s.substr(start, tab == std::string::npos ? std::string::npos : tab - start));
            if (tab == std::string::npos)
                return out;
            start = tab + 1;
        }
    }
} // namespace

TEST(Beacon, MatchesTheGoldenCapture)
{
    // goldens/beacon.bin is one beacon the old server sent (test_beacon.py).
    // Its host, PID, paths and port are that run's; formatting the same
    // fields must give the same bytes.
    std::ifstream in(std::string(VS_CONFORMANCE_DIR) + "/conformance/goldens/beacon.bin", std::ios::binary);
    ASSERT_TRUE(in) << "no goldens/beacon.bin";
    std::stringstream ss;
    ss << in.rdbuf();
    const std::string golden = ss.str();
    ASSERT_FALSE(golden.empty());
    ASSERT_EQ(golden.back(), '\n');

    const auto f = split_tabs(golden.substr(0, golden.size() - 1));
    ASSERT_EQ(f.size(), 12u);
    BeaconInfo info;
    info.host       = f[0];
    info.port       = static_cast<uint16_t>(std::stoi(f[1]));
    info.user       = f[2];
    info.pid        = std::stol(f[3]);
    info.sim_dir    = f[4];
    info.executable = f[5];
    info.input_file = f[6];
    info.version    = f[7] + "  \n"; // exec_get_current_version() may end in white space
    info.user_tag   = f[8];
    EXPECT_EQ(f[9], f[1]);
    info.enabled   = f[10] == "1";
    info.exec_mode = std::stoi(f[11]);

    EXPECT_EQ(format_beacon(info), golden);
}

TEST(Beacon, Fields)
{
    BeaconInfo info;
    info.host       = "h";
    info.port       = 40000;
    info.user       = "u";
    info.pid        = 1234;
    info.sim_dir    = "/sims/SIM_x";
    info.executable = "S_main_Linux.exe";
    info.input_file = "RUN_test/input.py";
    info.version    = "25.1.0";
    info.user_tag   = "tag";
    info.enabled    = false;
    info.exec_mode  = 5;
    EXPECT_EQ(format_beacon(info),
              "h\t40000\tu\t1234\t/sims/SIM_x\tS_main_Linux.exe\tRUN_test/input.py\t25.1.0\ttag\t40000\t0\t5\n");
    // The old 1024-byte buffer cut a long path off, newline included.
    info.sim_dir = std::string(2000, 'd');
    EXPECT_EQ(format_beacon(info).back(), '\n');
}

TEST(Beacon, SendsToEveryGroup)
{
    // Two unicast receivers stand in for the groups, so the test needs no multicast.
    Address a, b;
    const int ra = udp_socket(&a);
    const int rb = udp_socket(&b);
    ASSERT_NE(a.port(), b.port());
    // Beacon::open takes one port for all groups, so send to each receiver's port in turn.
    for (const Address& r : { a, b })
    {
        auto beacon = Beacon::open(system_interface(), { "127.0.0.1" }, r.port());
        ASSERT_TRUE(beacon) << beacon.error().message;
        ASSERT_TRUE(beacon.value().send("beacon\n"));
    }
    char buf[32];
    ASSERT_TRUE(readable(ra, 1000));
    EXPECT_EQ(std::string(buf, static_cast<std::size_t>(::recv(ra, buf, sizeof buf, 0))), "beacon\n");
    ASSERT_TRUE(readable(rb, 1000));
    EXPECT_EQ(std::string(buf, static_cast<std::size_t>(::recv(rb, buf, sizeof buf, 0))), "beacon\n");
    ::close(ra);
    ::close(rb);
}

TEST(Beacon, DefaultGroups)
{
    auto beacon = Beacon::open();
    ASSERT_TRUE(beacon);
    ASSERT_EQ(beacon.value().destinations().size(), 2u);
    EXPECT_EQ(beacon.value().destinations()[0].to_string(), "239.3.14.15:9265");
    EXPECT_EQ(beacon.value().destinations()[1].to_string(), "224.3.14.15:9265");
    EXPECT_FALSE(Beacon::open(system_interface(), { "not-an-address" }));
}

// ---------------------------------------------------------------------------
// ListenLoop
// ---------------------------------------------------------------------------

namespace
{
    class TestPolicy : public ListenPolicy
    {
        public:
            std::atomic<bool> open { true };
            std::function<bool(const Address&)> filter = [](const Address&) { return true; };
            std::string beacon_text                    = "beacon\n";

            std::mutex mutex;
            std::vector<std::unique_ptr<TcpConnection>> clients;
            std::vector<std::string> logs;
            std::atomic<int> beacons { 0 };

            bool accepting() override { return open; }

            bool allowed(const Address& a) override { return filter(a); }

            void connected(std::unique_ptr<TcpConnection> c, const Listener&) override
            {
                std::lock_guard<std::mutex> lock(mutex);
                clients.push_back(std::move(c));
            }

            std::string beacon_message(const Listener&) override
            {
                ++beacons;
                return beacon_text;
            }

            void log(const std::string& m, bool) override
            {
                std::lock_guard<std::mutex> lock(mutex);
                logs.push_back(m);
            }

            std::size_t client_count()
            {
                std::lock_guard<std::mutex> lock(mutex);
                return clients.size();
            }

            std::string all_logs()
            {
                std::lock_guard<std::mutex> lock(mutex);
                std::string s;
                for (auto& l : logs)
                    s += l + "|";
                return s;
            }
    };

    /** A ListenLoop on 127.0.0.1, run on its own thread. */
    struct RunningLoop
    {
            TestPolicy& policy;
            std::unique_ptr<ListenLoop> loop;
            uint16_t port = 0;
            std::thread thread;

            RunningLoop(TestPolicy& p, std::optional<Beacon> beacon = std::nullopt,
                        std::chrono::milliseconds period = ListenLoop::default_beacon_period,
                        SystemInterface& sys = system_interface())
                : policy(p)
            {
                auto l = ListenLoop::create(policy, std::move(beacon), {}, sys);
                EXPECT_TRUE(l);
                loop = std::move(l.value());
                loop->set_beacon_period(period);
                auto listener = Listener::open(sys, "127.0.0.1", 0);
                EXPECT_TRUE(listener);
                port = listener.value().port();
                loop->add(std::move(listener.value()));
                thread = std::thread([this] { loop->run(); });
            }

            ~RunningLoop()
            {
                loop->stop();
                thread.join();
            }

            Address address() const { return *Address::parse("127.0.0.1", port); }
    };
} // namespace

TEST(ListenLoop, AcceptsClients)
{
    TestPolicy policy;
    RunningLoop running(policy);
    const int a = tcp_client(running.address());
    const int b = tcp_client(running.address());
    ASSERT_GE(a, 0);
    ASSERT_GE(b, 0);
    EXPECT_TRUE(eventually([&] { return policy.client_count() == 2; }));
    {
        std::lock_guard<std::mutex> lock(policy.mutex);
        for (auto& c : policy.clients)
            EXPECT_TRUE(c->peer().is_loopback());
    }
    ::close(a);
    ::close(b);
}

TEST(ListenLoop, ClosedServerDisconnectsAtOnce)
{
    TestPolicy policy;
    policy.open = false;
    RunningLoop running(policy);
    const int c = tcp_client(running.address());
    ASSERT_GE(c, 0);
    EXPECT_TRUE(closed_by_peer(c, 2000));
    EXPECT_EQ(policy.client_count(), 0u);
    ::close(c);

    policy.open  = true;
    const int c2 = tcp_client(running.address());
    EXPECT_TRUE(eventually([&] { return policy.client_count() == 1; }));
    ::close(c2);
}

TEST(ListenLoop, RefusedAddressIsLoggedAndClosed)
{
    TestPolicy policy;
    policy.filter = [](const Address&) { return false; };
    RunningLoop running(policy);
    const int c = tcp_client(running.address());
    ASSERT_GE(c, 0);
    EXPECT_TRUE(closed_by_peer(c, 2000));
    EXPECT_EQ(policy.client_count(), 0u);
    EXPECT_TRUE(eventually([&] { return policy.all_logs().find("ILLEGAL IP CONNECTION ATTEMPTED: 127.0.0.1") != std::string::npos; }));
    ::close(c);
}

TEST(ListenLoop, SendsTheBeaconEachPeriod)
{
    Address receiver;
    const int r = udp_socket(&receiver);
    auto beacon = Beacon::open(system_interface(), { "127.0.0.1" }, receiver.port());
    ASSERT_TRUE(beacon);
    TestPolicy policy;
    {
        RunningLoop running(policy, std::move(beacon.value()), std::chrono::milliseconds(50));
        // The first beacon goes out at once, then one each period.
        ASSERT_TRUE(readable(r, 1000));
        EXPECT_TRUE(eventually([&] { return policy.beacons >= 4; }, 2000));
    }
    char buf[64];
    EXPECT_EQ(std::string(buf, static_cast<std::size_t>(::recv(r, buf, sizeof buf, 0))), "beacon\n");
    ::close(r);
}

TEST(ListenLoop, NoBeaconWhenTheMessageIsEmpty)
{
    Address receiver;
    const int r = udp_socket(&receiver);
    auto beacon = Beacon::open(system_interface(), { "127.0.0.1" }, receiver.port());
    ASSERT_TRUE(beacon);
    TestPolicy policy;
    policy.beacon_text = "";
    {
        RunningLoop running(policy, std::move(beacon.value()), std::chrono::milliseconds(20));
        EXPECT_TRUE(eventually([&] { return policy.beacons >= 3; }));
    }
    EXPECT_FALSE(readable(r, 100));
    ::close(r);
}

TEST(ListenLoop, StopReturnsPromptly)
{
    TestPolicy policy;
    auto l = ListenLoop::create(policy, std::nullopt);
    ASSERT_TRUE(l);
    ListenLoop& loop = *l.value();
    std::thread t([&] { loop.run(); });
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
    const auto start = std::chrono::steady_clock::now();
    loop.stop();
    t.join();
    EXPECT_LT(std::chrono::steady_clock::now() - start, std::chrono::milliseconds(500));
}

TEST(ListenLoop, AcceptFailureIsLoggedAndTheLoopGoesOn)
{
    HookedSystem sys;
    std::atomic<int> failures { 0 };
    sys.on_accept = [&](int fd, sockaddr* a, socklen_t* l) {
        // Fail the first accept with EMFILE, then behave.
        if (failures++ == 0)
            return fail_with(EMFILE);
        return ::accept(fd, a, l);
    };
    TestPolicy policy;
    RunningLoop running(policy, std::nullopt, ListenLoop::default_beacon_period, sys);
    const int c = tcp_client(running.address());
    ASSERT_GE(c, 0);
    EXPECT_TRUE(eventually([&] { return policy.client_count() == 1; }));
    EXPECT_NE(policy.all_logs().find("accept"), std::string::npos);
    ::close(c);
}
