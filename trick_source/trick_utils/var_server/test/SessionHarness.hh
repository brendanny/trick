/*
PURPOSE: (Fakes for running a Session without a simulation or a socket.)

FakeHost records what a session asks of the server; StringOutput collects
what it sends. run_case_in_session() runs a golden case script through a
real Session, so the core test (on the conformance model) and the adapter
test (on the Memory Manager) check the session against the Phase 0
captures, as GoldenReplay.hh does for the parser and encoders alone.
*/

#ifndef VS_TEST_SESSIONHARNESS_HH
#define VS_TEST_SESSIONHARNESS_HH

#include "GoldenReplay.hh"

#include "trick/vs/Session.hh"
#include "trick/vs/testing/Fakes.hh"

#include <atomic>
#include <functional>
#include <limits>
#include <map>
#include <mutex>
#include <string>
#include <vector>

#include <unistd.h>

namespace vs_test
{
    using namespace Trick::vs;
    using namespace Trick::vs::testing;

    class FakeHost : public SessionHost
    {
        public:
            /** Wraps each memory read; the adapter test holds the Memory Manager lock here. */
            std::function<void(const std::function<void()>&)> memory;
            std::atomic<bool> is_enabled { true };
            std::atomic<bool> python { true };
            std::atomic<bool> info { false };
            /** What run_python does: return an error message, or "" for success. */
            std::function<std::string(std::string_view)> python_runner;
            std::map<SieFile, std::string> sie_paths;
            std::atomic<int> schedule_changes { 0 };

            mutable std::mutex mutex;
            std::vector<std::string> python_lines;
            std::vector<cmd::VarSet> sets;
            std::vector<std::pair<LogLevel, std::string>> messages;
            std::vector<std::string> session_lines;
            std::vector<std::pair<int, std::string>> stdio;
            std::vector<std::string> tags;

            void read_memory(const std::function<void()>& read) override
            {
                if (memory)
                    memory(read);
                else
                    read();
            }

            bool enabled() const override { return is_enabled.load(); }

            Expected<void> run_python(std::string_view text) override
            {
                {
                    std::lock_guard<std::mutex> g(mutex);
                    python_lines.emplace_back(text);
                }
                if (python_runner)
                {
                    const std::string error = python_runner(text);
                    if (!error.empty())
                        return Error { error };
                }
                return {};
            }

            bool python_commands() const override { return python.load(); }

            int var_set(const cmd::VarSet& c) override
            {
                std::lock_guard<std::mutex> g(mutex);
                sets.push_back(c);
                return 0;
            }

            std::string sie_file(SieFile which) override { return sie_paths[which]; }

            void schedule_changed() override { ++schedule_changes; }

            bool info_messages() const override { return info.load(); }

            void message(LogLevel level, std::string_view text) override
            {
                std::lock_guard<std::mutex> g(mutex);
                messages.emplace_back(level, std::string(text));
            }

            void session_log(int, std::string_view text) override
            {
                std::lock_guard<std::mutex> g(mutex);
                session_lines.emplace_back(text);
            }

            void local_stdio(int stream, std::string_view text) override
            {
                std::lock_guard<std::mutex> g(mutex);
                stdio.emplace_back(stream, std::string(text));
            }

            void client_tag(std::string_view tag) override
            {
                std::lock_guard<std::mutex> g(mutex);
                tags.emplace_back(tag);
            }

            /** True if a message at `level` contains `text`. */
            bool logged(LogLevel level, const std::string& text) const
            {
                std::lock_guard<std::mutex> g(mutex);
                for (const auto& m : messages)
                    if (m.first == level && m.second.find(text) != std::string::npos)
                        return true;
                return false;
            }

            bool session_logged(const std::string& text) const
            {
                std::lock_guard<std::mutex> g(mutex);
                for (const auto& l : session_lines)
                    if (l.find(text) != std::string::npos)
                        return true;
                return false;
            }
    };

    /** A SessionOutput that keeps what is sent; `capacity` bytes until take() empties it. */
    class StringOutput : public SessionOutput
    {
        public:
            std::string bytes;
            std::vector<std::string> messages;
            std::size_t capacity = std::numeric_limits<std::size_t>::max() / 2;
            std::size_t chunk    = 65536;

            bool send(std::string_view m) override
            {
                if (m.size() > space())
                    return false;
                bytes.append(m.data(), m.size());
                messages.emplace_back(m);
                return true;
            }

            std::size_t space() const override { return capacity > bytes.size() ? capacity - bytes.size() : 0; }

            std::size_t file_chunk() const override { return chunk; }

            /** Everything sent so far; the queue is then empty. */
            std::string take()
            {
                std::string out;
                out.swap(bytes);
                messages.clear();
                return out;
            }
    };

    /** Change the working directory for a scope (send_file paths are relative to the SIM directory). */
    class ScopedChdir
    {
        public:
            explicit ScopedChdir(const std::string& dir)
            {
                char buf[4096];
                if (::getcwd(buf, sizeof buf) != nullptr)
                    _old = buf;
                _ok = ::chdir(dir.c_str()) == 0;
            }
            ~ScopedChdir()
            {
                if (!_old.empty())
                    (void)::chdir(_old.c_str());
            }
            bool ok() const noexcept { return _ok; }

        private:
            std::string _old;
            bool _ok = false;
    };

    /** Run a golden case's script through a Session with `host`, as one batch, and return what it sent. */
    inline std::string run_case_in_session(const GoldenCase& gc, Resolver& resolver, UnitConverter& units,
                                           const Clock& clock, SessionHost& host)
    {
        ScopedChdir in_sim(VS_CONFORMANCE_DIR);
        EXPECT_TRUE(in_sim.ok());
        StringOutput out;
        SessionConfig config;
        Session session(host, resolver, units, clock, clock, out, config);
        session.start();
        session.handle_batch(gc.script);
        // A file is sent in one go here: the output never fills.
        session.continue_file();
        EXPECT_FALSE(session.busy()) << gc.name;
        return out.take();
    }

    /** As above, with a FakeHost whose memory reads go through `memory`. */
    inline std::string run_case_in_session(const GoldenCase& gc, Resolver& resolver, UnitConverter& units,
                                           const Clock& clock,
                                           std::function<void(const std::function<void()>&)> memory = {})
    {
        FakeHost host;
        host.memory = std::move(memory);
        return run_case_in_session(gc, resolver, units, clock, host);
    }

} // namespace vs_test

#endif
