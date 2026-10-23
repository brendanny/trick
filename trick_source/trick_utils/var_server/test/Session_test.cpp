// Phase 5: Session and SessionRegistry with fakes. The golden cases run
// through a real Session; the rest checks the modes, the main thread's
// copies, file transfer, Python fallback, and the thread split.

#include "ConformanceModel.hh"
#include "SessionHarness.hh"
#include "UdunitsConverter.hh"

#include "trick/vs/FixedReply.hh"
#include "trick/vs/SessionRegistry.hh"

#include <atomic>
#include <cstdio>
#include <fstream>
#include <memory>
#include <string>
#include <thread>

#include <gtest/gtest.h>

using namespace vs_test;

namespace
{
    std::unique_ptr<UnitConverter> make_units(bool* real)
    {
#ifdef VS_HAVE_UDUNITS
        auto u = std::make_unique<UdunitsConverter>();
        if (u->ok())
        {
            *real = true;
            return u;
        }
#endif
        *real  = false;
        auto f = std::make_unique<FakeUnitConverter>();
        for (const char* n : { "m", "s", "1", "rad", "m/s", "degC" })
            f->add_name(n, n);
        return f;
    }

    class SessionGolden : public ::testing::TestWithParam<GoldenCase>
    {
    };

    /** A session on a small model, with its host, output and clock. */
    struct Fixture
    {
            FakeResolver model;
            FakeUnitConverter units;
            FakeClock clock;
            FakeHost host;
            StringOutput out;
            std::unique_ptr<Session> session;
            std::shared_ptr<FakeVariable> x;
            int wakes = 0;

            explicit Fixture(SessionConfig config = {})
            {
                x = model.set_scalar("a.x", WireType::Integer, 7, "m");
                model.set_scalar("a.y", WireType::Double, 2.5, "m");
                units.add("m", "ft", 3.28084);
                units.add_name("m", "m");
                units.add_name("ft", "ft");
                clock.tics_per_second = 1000;
                session = std::make_unique<Session>(host, model, units, clock, clock, out, config);
                session->set_waker([this] { ++wakes; });
                session->start();
            }

            void run(const std::string& lines) { session->handle_batch(lines); }

            void set_x(int v) { std::memcpy(x->bytes.data(), &v, sizeof v); }
    };

} // namespace

// ----------------------------------------------------------------------
// The golden cases through a real Session
// ----------------------------------------------------------------------

TEST_P(SessionGolden, MatchesTheCapture)
{
    const GoldenCase& gc = GetParam();
    bool real_units      = false;
    auto units           = make_units(&real_units);
    const std::string why = case_precondition(gc, real_units);
    if (why == "python")
        return; // the adapter's conformance run covers these with the real interpreter
    if (!why.empty())
        GTEST_SKIP() << why;
    FakeResolver model;
    build_conformance_model(model);
    ConformanceResolver resolver(model);
    FakeClock clock;
    check_case_output(gc, run_case_in_session(gc, resolver, *units, clock));
}

INSTANTIATE_TEST_SUITE_P(Conformance, SessionGolden, ::testing::ValuesIn(golden_cases),
                         [](const ::testing::TestParamInfo<GoldenCase>& info) { return std::string(info.param.name); });

// ----------------------------------------------------------------------
// Commands
// ----------------------------------------------------------------------

TEST(Session, CommandsRunWhenTheyArrive)
{
    Fixture f;
    f.run("trick.var_add(\"a.x\")\ntrick.var_send()\n");
    EXPECT_EQ(f.out.take(), "0\t7\n");
    f.run("trick.var_send_list_size()\n");
    EXPECT_EQ(f.out.take(), "3\t1\n");
}

TEST(Session, UnitsApplyToTheFirstMatchOnly)
{
    Fixture f;
    f.run("trick.var_add(\"a.y\")\ntrick.var_add(\"a.y\")\ntrick.var_units(\"a.y\", \"ft\")\ntrick.var_send()\n");
    EXPECT_EQ(f.out.take(), "0\t8.2021 {ft}\t2.5\n");
}

TEST(Session, BadUnitsAreLoggedAndChangeNothing)
{
    Fixture f;
    f.run("trick.var_add(\"a.y\", \"furlong\")\ntrick.var_send()\n");
    EXPECT_EQ(f.out.take(), "0\t2.5\n");
    EXPECT_TRUE(f.host.logged(LogLevel::Error, "furlong"));
}

TEST(Session, AnUnknownNameIsBadRefAndLogged)
{
    Fixture f;
    f.run("trick.var_add(\"a.nope\")\ntrick.var_send()\n");
    EXPECT_EQ(f.out.take(), "0\tBAD_REF\n");
    EXPECT_TRUE(f.host.logged(LogLevel::Error, "could not find variable a.nope"));
}

TEST(Session, RemoveTakesTheFirstMatchAndClearEmptiesTheList)
{
    Fixture f;
    f.run("trick.var_add(\"a.x\")\ntrick.var_add(\"a.y\")\ntrick.var_add(\"a.x\")\ntrick.var_remove(\"a.x\")\n"
          "trick.var_send()\n");
    EXPECT_EQ(f.out.take(), "0\t2.5\t7\n");
    f.run("trick.var_clear()\ntrick.var_send()\n");
    EXPECT_EQ(f.out.take(), ""); // an empty list sends nothing
}

TEST(Session, SendOnceChecksTheCount)
{
    Fixture f;
    f.run("trick.var_send_once(\"a.x,a.y\", 2)\n");
    EXPECT_EQ(f.out.take(), "5\t7\t2.5\n");
    f.run("trick.var_send_once(\"a.x,a.y\")\n");
    EXPECT_EQ(f.out.take(), "");
    EXPECT_TRUE(f.host.logged(LogLevel::Error, "does not match num_vars"));
}

TEST(Session, TimeIsTheTimeOfTheCopy)
{
    Fixture f;
    f.clock.time = 2500; // 2.5 s at 1000 tics per second
    f.run("trick.var_add(\"time\")\ntrick.var_send()\n");
    EXPECT_EQ(f.out.take(), "0\t2.5 {s}\n");
}

TEST(Session, BinaryKeepsNoNamesAsTheOldServer)
{
    Fixture f;
    f.run("trick.var_binary_nonames()\ntrick.var_binary()\ntrick.var_add(\"a.x\")\ntrick.var_send()\n");
    const std::string b = f.out.take();
    // header (12) + type (4) + size (4) + value (4): no name
    EXPECT_EQ(b.size(), 24u);
    f.run("trick.var_ascii()\ntrick.var_send()\n");
    EXPECT_EQ(f.out.take(), "0\t7\n");
}

TEST(Session, ExistsAndListSizeAreFixedReplies)
{
    Fixture f;
    f.run("trick.var_exists(\"a.x\")\ntrick.var_exists(\"a.q\")\n");
    EXPECT_EQ(f.out.take(), var_exists_reply(true, false) + var_exists_reply(false, false));
}

TEST(Session, ZeroCycleIsRefused)
{
    Fixture f;
    f.run("trick.var_cycle(0.0)\n");
    EXPECT_DOUBLE_EQ(f.session->cycle_s(), 0.1);
    EXPECT_TRUE(f.host.logged(LogLevel::Error, "var_cycle"));
    f.run("trick.var_cycle(0.25)\n");
    EXPECT_DOUBLE_EQ(f.session->cycle_s(), 0.25);
}

TEST(Session, ZeroFrameMultipleIsRefused)
{
    Fixture f;
    f.run("trick.var_set_copy_mode(2)\ntrick.var_set_frame_multiple(0)\ntrick.var_add(\"a.x\")\n");
    f.session->main_copy_top(5);
    f.session->on_deadline();
    EXPECT_EQ(f.out.take(), "0\t7\n"); // multiple stays 1: every frame
}

TEST(Session, ExitEndsTheSession)
{
    Fixture f;
    f.run("trick.var_exit()\ntrick.var_add(\"a.x\")\n");
    EXPECT_TRUE(f.session->exiting());
}

TEST(Session, ClientTagGoesToTheHostAndTheLogs)
{
    Fixture f;
    f.host.info = true;
    f.run("trick.var_set_client_tag(\"panel\")\n");
    f.run("trick.var_add(\"a.x\")\n");
    ASSERT_EQ(f.host.tags.size(), 1u);
    EXPECT_EQ(f.host.tags[0], "panel");
    EXPECT_TRUE(f.host.logged(LogLevel::Debug, "tag=<panel>"));
}

TEST(Session, ServerLogsEveryBatchWhenAsked)
{
    SessionConfig c;
    c.log         = true;
    c.session_log = true;
    c.peer_host   = "10.0.0.5";
    c.peer_port   = 4242;
    Fixture f(c);
    EXPECT_TRUE(f.host.session_logged("Variable Server Session started with 10.0.0.5:4242"));
    f.run("trick.var_add(\"a.x\")\n");
    EXPECT_TRUE(f.host.logged(LogLevel::Playback, "trick.var_add(\"a.x\")"));
    EXPECT_TRUE(f.host.session_logged("trick.var_add(\"a.x\")"));
}

// ----------------------------------------------------------------------
// Asynchronous copies and writes
// ----------------------------------------------------------------------

TEST(SessionAsync, EachDeadlineCopiesAndSends)
{
    Fixture f;
    f.run("trick.var_add(\"a.x\")\n");
    f.session->on_deadline();
    EXPECT_EQ(f.out.take(), "0\t7\n");
    f.set_x(8);
    f.session->on_deadline();
    EXPECT_EQ(f.out.take(), "0\t8\n");
}

TEST(SessionAsync, PauseStopsWritesButNotVarSend)
{
    Fixture f;
    f.run("trick.var_add(\"a.x\")\ntrick.var_pause()\n");
    f.session->on_deadline();
    EXPECT_EQ(f.out.take(), "");
    f.run("trick.var_send()\n");
    EXPECT_EQ(f.out.take(), "0\t7\n");
    f.run("trick.var_unpause()\n");
    f.session->on_deadline();
    EXPECT_EQ(f.out.take(), "0\t7\n");
}

TEST(SessionAsync, ADisabledServerSendsNothing)
{
    Fixture f;
    f.run("trick.var_add(\"a.x\")\n");
    f.host.is_enabled = false;
    f.session->on_deadline();
    EXPECT_EQ(f.out.take(), "");
}

TEST(SessionAsync, AFullQueueDropsTheClient)
{
    Fixture f;
    f.out.capacity = 3;
    f.run("trick.var_add(\"a.x\")\n");
    f.session->on_deadline();
    EXPECT_TRUE(f.session->exiting());
    EXPECT_TRUE(f.host.logged(LogLevel::Error, "not reading"));
}

// ----------------------------------------------------------------------
// The main thread's copies
// ----------------------------------------------------------------------

TEST(SessionScheduled, ModeChangeSetsTheNextTimeOnTheMainThread)
{
    Fixture f;
    f.clock.time = 1234;
    f.run("trick.var_cycle(0.5)\ntrick.var_set_copy_mode(1)\n");
    EXPECT_EQ(f.host.schedule_changes.load(), 2);
    EXPECT_EQ(f.session->next_tics(), never_tics); // not until the main thread looks
    f.session->main_refresh(1234, 0);
    EXPECT_EQ(f.session->next_tics(), 1500);
    EXPECT_EQ(f.session->freeze_next_tics(), 500);
    f.session->main_refresh(9999, 0); // no change since: nothing moves
    EXPECT_EQ(f.session->next_tics(), 1500);
    f.session->main_refresh(200, 0, true); // a checkpoint load took sim time back
    EXPECT_EQ(f.session->next_tics(), 500);
}

TEST(SessionScheduled, TheMainThreadCopiesAndTheRunnerSendsOnce)
{
    Fixture f;
    f.run("trick.var_add(\"a.x\")\ntrick.var_set_copy_mode(1)\n");
    f.session->main_refresh(0, 0);
    EXPECT_EQ(f.session->next_tics(), 100);
    f.session->main_copy_scheduled(50); // not due
    f.session->on_deadline();
    EXPECT_EQ(f.out.take(), "");
    f.session->main_copy_scheduled(100);
    EXPECT_EQ(f.session->next_tics(), 200);
    f.set_x(9); // after the copy: the frame keeps 7
    f.session->on_deadline();
    EXPECT_EQ(f.out.take(), "0\t7\n");
    f.session->on_deadline(); // nothing new copied: nothing sent
    EXPECT_EQ(f.out.take(), "");
    EXPECT_EQ(f.wakes, 0); // async write: the runner sends on its own cycle
}

TEST(SessionScheduled, AFrameFromAnOlderListIsNotSent)
{
    Fixture f;
    f.run("trick.var_add(\"a.x\")\ntrick.var_set_copy_mode(1)\n");
    f.session->main_refresh(0, 0);
    f.session->main_copy_scheduled(100);
    f.run("trick.var_add(\"a.y\")\n");
    f.session->on_deadline();
    EXPECT_EQ(f.out.take(), "");
    f.session->main_copy_scheduled(200);
    f.session->on_deadline();
    EXPECT_EQ(f.out.take(), "0\t7\t2.5\n");
}

TEST(SessionScheduled, WhenCopiedInRealTimeWakesTheRunner)
{
    Fixture f;
    f.clock.is_real_time = true;
    f.run("trick.var_add(\"a.x\")\ntrick.var_sync(2)\n");
    f.session->main_refresh(0, 0);
    f.session->on_deadline(); // write mode is when-copied: the deadline sends nothing
    f.session->main_copy_scheduled(100);
    EXPECT_EQ(f.wakes, 1);
    f.session->on_wake();
    EXPECT_EQ(f.out.take(), "0\t7\n");
    f.session->on_deadline();
    EXPECT_EQ(f.out.take(), "");
}

TEST(SessionScheduled, WhenCopiedNotInRealTimeSendsOnTheCycle)
{
    Fixture f;
    f.run("trick.var_add(\"a.x\")\ntrick.var_sync(2)\n");
    f.session->main_refresh(0, 0);
    f.session->main_copy_scheduled(100);
    EXPECT_EQ(f.wakes, 0);
    f.session->on_wake();
    EXPECT_EQ(f.out.take(), "");
    f.session->on_deadline();
    EXPECT_EQ(f.out.take(), "0\t7\n");
}

TEST(SessionScheduled, PausedFramesWaitForUnpause)
{
    Fixture f;
    f.clock.is_real_time = true;
    f.run("trick.var_add(\"a.x\")\ntrick.var_sync(2)\ntrick.var_pause()\n");
    f.session->main_refresh(0, 0);
    f.session->main_copy_scheduled(100);
    EXPECT_EQ(f.wakes, 0);
    f.session->on_wake();
    EXPECT_EQ(f.out.take(), "");
}

TEST(SessionScheduled, BackToAsyncStopsMainThreadCopies)
{
    Fixture f;
    f.run("trick.var_add(\"a.x\")\ntrick.var_set_copy_mode(1)\n");
    f.session->main_refresh(0, 0);
    f.run("trick.var_set_copy_mode(0)\n");
    f.session->main_refresh(0, 0);
    EXPECT_EQ(f.session->next_tics(), never_tics);
}

TEST(SessionScheduled, BadModesAreRefused)
{
    Fixture f;
    f.run("trick.var_set_copy_mode(7)\ntrick.var_set_write_mode(3)\n");
    EXPECT_TRUE(f.host.logged(LogLevel::Error, "var_set_copy_mode(7)"));
    EXPECT_EQ(f.host.schedule_changes.load(), 0);
}

TEST(SessionTopOfFrame, CopiesOnSelectedFrames)
{
    Fixture f;
    f.run("trick.var_add(\"a.x\")\ntrick.var_set_copy_mode(2)\ntrick.var_set_frame_multiple(3)\n"
          "trick.var_set_frame_offset(1)\n");
    for (long long frame = 0; frame < 7; ++frame)
    {
        f.set_x(static_cast<int>(frame));
        f.session->main_copy_top(frame);
        f.session->on_deadline();
    }
    EXPECT_EQ(f.out.take(), "0\t1\n0\t4\n");
}

TEST(SessionFreeze, FreezeInitStartsOneCycleIn)
{
    Fixture f;
    f.run("trick.var_add(\"a.x\")\ntrick.var_set_copy_mode(1)\n");
    f.session->main_freeze_init();
    EXPECT_EQ(f.session->freeze_next_tics(), 100);
    f.session->main_copy_freeze_scheduled(100);
    EXPECT_EQ(f.session->freeze_next_tics(), 200);
    f.session->on_deadline();
    EXPECT_EQ(f.out.take(), "0\t7\n");
}

TEST(SessionFreeze, TopOfFrameUsesTheFreezeFrameSettings)
{
    Fixture f;
    f.run("trick.var_add(\"a.x\")\ntrick.var_set_copy_mode(2)\ntrick.var_set_freeze_frame_multiple(2)\n"
          "trick.var_set_freeze_frame_offset(1)\n");
    f.session->main_copy_freeze(2);
    f.session->on_deadline();
    EXPECT_EQ(f.out.take(), "");
    f.session->main_copy_freeze(3);
    f.session->on_deadline();
    EXPECT_EQ(f.out.take(), "0\t7\n");
}

// ----------------------------------------------------------------------
// Files
// ----------------------------------------------------------------------

namespace
{
    std::string temp_file(const std::string& contents)
    {
        char name[] = "/tmp/vs_session_file_XXXXXX";
        const int fd = ::mkstemp(name);
        EXPECT_GE(fd, 0);
        if (fd >= 0)
        {
            EXPECT_EQ(::write(fd, contents.data(), contents.size()), static_cast<ssize_t>(contents.size()));
            ::close(fd);
        }
        return name;
    }
} // namespace

TEST(SessionFile, ChunksWhileTheQueueHasSpaceAndKeepsRepliesInOrder)
{
    Fixture f;
    std::string contents;
    for (int i = 0; i < 1000; ++i)
        contents += "line " + std::to_string(i) + "\n";
    const std::string path = temp_file(contents);
    f.out.capacity = 1000;
    f.out.chunk    = 300;
    f.run("trick.send_file(\"" + path + "\")\ntrick.var_exists(\"a.x\")\n");
    EXPECT_TRUE(f.session->busy());
    std::string got = f.out.take();
    for (int i = 0; i < 1000 && f.session->busy(); ++i)
    {
        f.session->continue_file();
        got += f.out.take();
    }
    EXPECT_FALSE(f.session->busy());
    EXPECT_EQ(got, file_header(contents.size()) + contents + var_exists_reply(true, false));
    std::remove(path.c_str());
}

TEST(SessionFile, NoAsyncWritesWhileAFileIsSent)
{
    Fixture f;
    const std::string path = temp_file(std::string(5000, 'z'));
    f.out.capacity = 2000;
    f.out.chunk    = 1000;
    f.run("trick.var_add(\"a.x\")\ntrick.send_file(\"" + path + "\")\n");
    f.session->on_deadline();
    std::string got = f.out.take();
    EXPECT_EQ(got.find("0\t7"), std::string::npos);
    std::remove(path.c_str());
}

TEST(SessionFile, AMissingFileGetsTheMissingReply)
{
    Fixture f;
    f.run("trick.send_file(\"/no/such/file\")\n");
    EXPECT_EQ(f.out.take(), file_missing_reply());
    EXPECT_TRUE(f.host.logged(LogLevel::Error, "Cannot open /no/such/file"));
}

TEST(SessionFile, SieFilesComeFromTheHost)
{
    Fixture f;
    const std::string path        = temp_file("<sie/>");
    f.host.sie_paths[SieFile::Enum] = path;
    f.run("trick.send_sie_enum()\n");
    EXPECT_EQ(f.out.take(), file_header(6) + "<sie/>");
    std::remove(path.c_str());
}

// ----------------------------------------------------------------------
// Python, stdio and var_set
// ----------------------------------------------------------------------

TEST(SessionPython, ALineThatIsNotTypedRunsInPython)
{
    Fixture f;
    f.run("x = 1 + 1\n");
    ASSERT_EQ(f.host.python_lines.size(), 1u);
    EXPECT_EQ(f.host.python_lines[0], "x = 1 + 1\n");
}

TEST(SessionPython, ErrorsGoToTheSessionLogAndOptionallyToTheClient)
{
    SessionConfig c;
    c.session_log = true;
    Fixture f(c);
    Session* s           = f.session.get();
    f.host.python_runner = [s](std::string_view) {
        // Python prints the traceback to sys.stderr, which shortcuts.py sends through var_write_stdio.
        s->execute(cmd::VarWriteStdio { 2, "NameError: name 'q' is not defined\n" });
        return std::string("python error");
    };
    f.run("q\n");
    EXPECT_TRUE(f.host.session_logged("NameError"));
    EXPECT_EQ(f.out.take(), ""); // no reply unless asked (decision 3)
    ASSERT_EQ(f.host.stdio.size(), 1u);
    f.run("trick.var_send_ip_errors(True)\n");
    f.run("q\n");
    EXPECT_EQ(f.out.take(), ip_error_reply("NameError: name 'q' is not defined\n"));
}

TEST(SessionPython, PythonCommandsCanBeTurnedOff)
{
    Fixture f;
    f.host.python = false;
    f.run("import os\n");
    EXPECT_TRUE(f.host.python_lines.empty());
    EXPECT_TRUE(f.host.logged(LogLevel::Warning, "Python commands are turned off"));
    f.run("trick.var_add(\"a.x\")\ntrick.var_send()\n"); // typed commands still run
    EXPECT_EQ(f.out.take(), "0\t7\n");
}

TEST(SessionPython, StdioGoesToTheClientWhenAsked)
{
    Fixture f;
    f.run("trick.var_write_stdio(1, \"hi\")\n");
    EXPECT_EQ(f.out.take(), "");
    ASSERT_EQ(f.host.stdio.size(), 1u);
    f.run("trick.var_set_send_stdio(True)\ntrick.var_write_stdio(1, \"hi\")\n");
    EXPECT_EQ(f.out.take(), stdio_reply(1, "hi"));
}

TEST(SessionPython, VarSetGoesToTheHost)
{
    Fixture f;
    f.run("trick.var_set(\"a.x\", 3)\n");
    ASSERT_EQ(f.host.sets.size(), 1u);
    EXPECT_EQ(f.host.sets[0].name, "a.x");
}

// ----------------------------------------------------------------------
// Connection list and registry
// ----------------------------------------------------------------------

TEST(SessionInfo, ConnectionJsonHasTheOldLayout)
{
    SessionConfig c;
    c.peer_host = "127.0.0.1";
    c.peer_port = 5000;
    Fixture f(c);
    f.run("trick.var_set_client_tag(\"tv\")\ntrick.var_add(\"a.x\")\ntrick.var_add(\"a.y\")\ntrick.var_binary()\n");
    EXPECT_EQ(f.session->connection_json(), "  \"connection\":{\n"
                                            "    \"client_tag\":\"tv\",\n"
                                            "    \"client_IP_address\":\"127.0.0.1\",\n"
                                            "    \"client_port\":\"5000\",\n"
                                            "    \"format\":\"BINARY\",\n"
                                            "    \"update_rate\":0.1,\n"
                                            "    \"variables\":[\n"
                                            "      \"a.x\",\n"
                                            "      \"a.y\"\n"
                                            "    ]\n"
                                            "  }\n");
}

TEST(SessionRegistry, JobTimesAreTheSmallestOfAnySession)
{
    Fixture a, b;
    SessionRegistry reg;
    std::shared_ptr<Session> sa(a.session.get(), [](Session*) {});
    std::shared_ptr<Session> sb(b.session.get(), [](Session*) {});
    reg.add(sa);
    reg.add(sb);
    EXPECT_EQ(reg.size(), 2u);
    a.run("trick.var_cycle(0.3)\ntrick.var_set_copy_mode(1)\n");
    b.run("trick.var_cycle(0.2)\ntrick.var_set_copy_mode(1)\n");
    auto t = reg.refresh(0, 0);
    EXPECT_EQ(t.next_tics, 200);
    EXPECT_EQ(reg.copy_scheduled(200), 300);
    reg.remove(sb.get());
    EXPECT_EQ(reg.size(), 1u);
    EXPECT_EQ(reg.job_times().next_tics, 300);
    EXPECT_EQ(reg.connections_json().rfind("{\"variable_server_connections\":[\n{\n", 0), 0u);
}

TEST(SessionRegistry, AnEmptyListIsValidJson)
{
    SessionRegistry reg;
    EXPECT_EQ(reg.connections_json(), "{\"variable_server_connections\":[\n]}\n");
}

// ----------------------------------------------------------------------
// The thread split: the main thread copies while the runner changes the list
// ----------------------------------------------------------------------

TEST(SessionThreads, MainThreadCopiesWhileTheRunnerChangesTheList)
{
    Fixture f;
    f.clock.is_real_time = true; // fixed for the test: the fake clock is not atomic
    f.run("trick.var_add(\"a.x\")\ntrick.var_set_copy_mode(2)\ntrick.var_set_write_mode(1)\n");
    std::atomic<bool> stop { false };
    std::atomic<long long> copies { 0 };
    std::thread main_thread([&] {
        long long frame = 0;
        while (!stop.load())
        {
            f.session->main_refresh(frame, 0);
            f.session->main_copy_top(frame++);
            f.session->main_copy_scheduled(frame * 10);
            ++copies;
        }
    });
    for (int i = 0; i < 2000; ++i)
    {
        f.run(i % 2 ? "trick.var_add(\"a.y\")\n" : "trick.var_remove(\"a.y\")\n");
        if (i % 7 == 0)
            f.run("trick.var_set_copy_mode(" + std::to_string(i % 3) + ")\n");
        f.session->on_wake();
        f.session->on_deadline();
        if (f.out.bytes.size() > 100000)
            f.out.take();
    }
    stop = true;
    main_thread.join();
    EXPECT_GT(copies.load(), 0);
    EXPECT_FALSE(f.session->exiting());
}

TEST(SessionThreads, JobsRunWhileSessionsComeAndGo)
{
    // The main thread walks the published vector while runners add and remove
    // sessions. The jobs must hold the vector they walk.
    SessionRegistry registry;
    std::vector<std::unique_ptr<Fixture>> fixtures;
    for (int i = 0; i < 4; ++i)
        fixtures.push_back(std::make_unique<Fixture>());
    std::atomic<bool> stop { false };
    std::thread main_thread([&] {
        long long t = 0;
        while (!stop)
        {
            registry.refresh(t, 0);
            registry.copy_scheduled(t);
            registry.copy_top(t);
            registry.job_times();
            ++t;
        }
    });
    for (int i = 0; i < 5000; ++i)
    {
        Session* s = fixtures[i % 4]->session.get();
        registry.add(std::shared_ptr<Session>(s, [](Session*) {}));
        registry.remove(s);
    }
    stop = true;
    main_thread.join();
    EXPECT_EQ(registry.size(), 0u);
}
