// Phase 2 exit test: the new parser and encoders give the bytes of every
// golden capture of test/SIM_vs_conformance.
//
// Each case script is parsed with parse_batch() and run by a small executor
// that does what the old session did for each command, with the variables of
// ConformanceModel.hh. The output is compared with goldens/<case>.bin.
//
// Cases that need Python (print, raise, a syntax error) or that write SIM
// memory (var_set) cannot run here; for those the test checks only how the
// script parses. Cases in EXPECTED_TO_CHANGE record a defect that the rewrite
// fixes: their structure must match, and each changed value must be the
// correctly swapped value of the same variable in the unswapped capture.

#include "ConformanceModel.hh"
#include "UdunitsConverter.hh"

#include "trick/vs/CommandParser.hh"
#include "trick/vs/FixedReply.hh"
#include "trick/vs/Packetizer.hh"
#include "trick/vs/Units.hh"

#include <cstdio>
#include <cstring>
#include <fstream>
#include <map>
#include <memory>
#include <set>
#include <sstream>
#include <string>
#include <vector>

#include <gtest/gtest.h>

#ifndef VS_CONFORMANCE_DIR
#error "VS_CONFORMANCE_DIR must name test/SIM_vs_conformance"
#endif

using namespace vs_test;

namespace
{

    struct GoldenCase
    {
            const char* name;
            const char* script;
            bool expected_to_change;
    };

    void PrintTo(const GoldenCase& c, std::ostream* os) { *os << c.name; }

    const GoldenCase golden_cases[] = {
#define VS_GOLDEN_CASE(name, script, changes) { name, script, changes },
#include "golden_cases.inc"
#undef VS_GOLDEN_CASE
    };

    std::string read_file(const std::string& path, bool* found = nullptr)
    {
        std::ifstream in(path, std::ios::binary);
        if (found)
            *found = static_cast<bool>(in);
        std::ostringstream ss;
        ss << in.rdbuf();
        return ss.str();
    }

    std::string golden(const std::string& name)
    {
        bool found = false;
        std::string bytes = read_file(std::string(VS_CONFORMANCE_DIR) + "/conformance/goldens/" + name + ".bin", &found);
        EXPECT_TRUE(found) << "no golden file for " << name;
        return bytes;
    }

    // ------------------------------------------------------------------
    // The executor: what the old VariableServerSession did per command.
    // ------------------------------------------------------------------

    struct SessionVar
    {
            std::unique_ptr<ResolvedVar> ref;
            std::shared_ptr<const Conversion> conversion;
            std::string units;
    };

    class Executor
    {
        public:
            Executor(Resolver& resolver, UnitConverter& units)
                : _resolver(resolver)
                , _units(units)
            {
            }

            std::string output;

            void run(const Command& c)
            {
                std::visit([this](const auto& cmd) { this->exec(cmd); }, c);
            }

        private:
            void exec(const cmd::VarPause&) {}

            void exec(const cmd::VarAdd& c)
            {
                SessionVar v;
                v.ref = _resolver.resolve(c.name);
                if (c.name == "time")
                    v.units = "s"; // the session's time variable always prints {s}
                _list.push_back(std::move(v));
                if (c.units)
                    set_units(c.name, *c.units);
            }

            void exec(const cmd::VarUnits& c) { set_units(c.name, c.units); }

            void exec(const cmd::VarRemove& c)
            {
                for (auto it = _list.begin(); it != _list.end(); ++it)
                {
                    if (it->ref->name() == c.name)
                    {
                        _list.erase(it);
                        return;
                    }
                }
            }

            void exec(const cmd::VarClear&) { _list.clear(); }

            void exec(const cmd::VarSend&) { send(_list, MessageType::VarList); }

            void exec(const cmd::VarSendOnce& c)
            {
                const std::vector<std::string> names = split_send_once_names(c.names);
                const std::size_t count              = c.count ? static_cast<std::size_t>(*c.count) : 1;
                if (names.size() != count)
                    return;
                std::vector<SessionVar> once;
                for (const std::string& n : names)
                {
                    SessionVar v;
                    v.ref = _resolver.resolve(n);
                    once.push_back(std::move(v));
                }
                send(once, MessageType::SendOnce);
            }

            void exec(const cmd::VarExists& c) { output += var_exists_reply(_resolver.resolve(c.name)->resolved(), _binary); }

            void exec(const cmd::VarSendListSize&)
            {
                output += list_size_reply(static_cast<int32_t>(_list.size()), _binary);
            }

            void exec(const cmd::VarGetStlSize& c) { output += stl_size_reply(_resolver.resolve(c.name)->stl_size(), _binary); }

            void exec(const cmd::VarAscii&) { _binary = false; }

            void exec(const cmd::VarBinary&) { _binary = true; }

            void exec(const cmd::VarBinaryNoNames&)
            {
                _binary  = true;
                _nonames = true;
            }

            void exec(const cmd::VarByteswap& c) { _byteswap = c.on; }

            void exec(const cmd::SendFile& c)
            {
                bool found        = false;
                const std::string data = read_file(std::string(VS_CONFORMANCE_DIR) + "/" + c.path, &found);
                if (!found)
                {
                    output += file_missing_reply();
                    return;
                }
                output += file_header(data.size());
                output += data;
            }

            template <class C> void exec(const C&) { ADD_FAILURE() << "the executor does not run " << command_name(C {}); }

            void set_units(const std::string& name, const std::string& units)
            {
                for (SessionVar& v : _list)
                {
                    if (v.ref->name() != name)
                        continue;
                    auto choice = choose_units(*v.ref, units, _units);
                    if (choice && choice.value())
                    {
                        v.conversion = choice.value()->conversion;
                        v.units      = choice.value()->units;
                    }
                    return; // the first match only, as the old server
                }
            }

            void send(const std::vector<SessionVar>& vars, MessageType type)
            {
                Snapshot snapshot;
                std::vector<VarFormat> formats;
                for (const SessionVar& v : vars)
                {
                    v.ref->stage(snapshot, false);
                    VarFormat f;
                    f.name       = v.ref->name();
                    f.conversion = v.conversion.get();
                    f.units      = v.units;
                    formats.push_back(f);
                }
                Packets packets;
                if (_binary)
                    encode_binary(packets, snapshot, formats, type, _nonames, _byteswap);
                else
                    encode_ascii(packets, snapshot, formats, type);
                for (const std::string& m : packets.messages)
                    output += m;
            }

            Resolver& _resolver;
            UnitConverter& _units;
            std::vector<SessionVar> _list;
            bool _binary   = false;
            bool _nonames  = false;
            bool _byteswap = false;
    };

    std::string run_script(const std::string& script, UnitConverter& units)
    {
        FakeResolver model;
        build_conformance_model(model);
        ConformanceResolver resolver(model);
        Executor ex(resolver, units);
        for (const Command& c : parse_batch(script))
            ex.run(c);
        return ex.output;
    }

    /** A converter that knows unit names but no conversions, when UDUNITS is not built in. */
    std::unique_ptr<UnitConverter> make_converter(bool* real)
    {
#ifdef VS_HAVE_UDUNITS
        auto u = std::make_unique<UdunitsConverter>();
        if (u->ok())
        {
            *real = true;
            return u;
        }
#endif
        *real   = false;
        auto f  = std::make_unique<FakeUnitConverter>();
        for (const char* n : { "m", "s", "1", "rad", "m/s", "degC" })
            f->add_name(n, n);
        return f;
    }

    // ------------------------------------------------------------------
    // Binary decoding, for the cases that change on purpose
    // ------------------------------------------------------------------

    struct DecodedVar
    {
            std::string name;
            int32_t type = 0;
            std::string value;
    };

    struct DecodedMessage
    {
            int32_t type = 0, size = 0, count = 0;
            std::vector<DecodedVar> vars;
    };

    int32_t get_int(const std::string& s, std::size_t& pos, bool swap)
    {
        unsigned char b[4];
        std::memcpy(b, s.data() + pos, 4);
        pos += 4;
        if (swap)
            std::swap(b[0], b[3]), std::swap(b[1], b[2]);
        int32_t v;
        std::memcpy(&v, b, 4);
        return v;
    }

    std::vector<DecodedMessage> decode(const std::string& s, bool names, bool swap)
    {
        std::vector<DecodedMessage> out;
        std::size_t pos = 0;
        while (pos + 12 <= s.size())
        {
            DecodedMessage m;
            m.type  = get_int(s, pos, swap);
            m.size  = get_int(s, pos, swap);
            m.count = get_int(s, pos, swap);
            for (int32_t i = 0; i < m.count; ++i)
            {
                DecodedVar v;
                if (names)
                {
                    const int32_t len = get_int(s, pos, swap);
                    v.name            = s.substr(pos, static_cast<std::size_t>(len));
                    pos += static_cast<std::size_t>(len);
                }
                v.type             = get_int(s, pos, swap);
                const int32_t size = get_int(s, pos, swap);
                v.value            = s.substr(pos, static_cast<std::size_t>(size));
                pos += static_cast<std::size_t>(size);
                m.vars.push_back(v);
            }
            out.push_back(m);
        }
        EXPECT_EQ(pos, s.size()) << "trailing bytes";
        return out;
    }

    /** Element size of a wire type, independent of the encoder. */
    std::size_t element_size(int32_t type, std::size_t value_size)
    {
        switch (static_cast<WireType>(type))
        {
            case WireType::Short:
            case WireType::UnsignedShort:
                return 2;
            case WireType::Integer:
            case WireType::UnsignedInteger:
            case WireType::Float:
            case WireType::WideCharacter:
            case WireType::WideString:
            case WireType::BadRef:
                return 4;
            case WireType::Long:
            case WireType::UnsignedLong:
            case WireType::LongLong:
            case WireType::UnsignedLongLong:
            case WireType::Double:
                return 8;
            case WireType::Bitfield:
            case WireType::UnsignedBitfield:
            case WireType::Enumerated:
                return value_size;
            default:
                return 1;
        }
    }

    std::string swap_elements(const std::string& v, std::size_t n)
    {
        std::string out = v;
        for (std::size_t i = 0; i + n <= out.size(); i += n)
            for (std::size_t k = 0; k < n / 2; ++k)
                std::swap(out[i + k], out[i + n - 1 - k]);
        return out;
    }

    /**
     * Check a byteswap case whose golden records a defect. The structure must
     * match the golden; a value may differ only if it is the unswapped
     * capture's value of the same variable, correctly swapped.
     */
    void check_changed_byteswap_case(const std::string& name, const std::string& got)
    {
        const bool nonames      = name.find("_nonames_") != std::string::npos;
        const std::string suffix = name.substr(name.rfind('_'));                          // "_strings", ...
        const std::string named_case = "byteswap" + suffix;                               // names in order
        const std::string reference  = "binary" + suffix;                                 // unswapped values

        const auto want     = decode(golden(name), !nonames, true);
        const auto have     = decode(got, !nonames, true);
        const auto names    = decode(golden(named_case), true, true);
        const auto unswapped = decode(golden(reference), true, false);

        std::map<std::string, DecodedVar> native;
        for (const auto& m : unswapped)
            for (const auto& v : m.vars)
                native[v.name] = v;

        ASSERT_EQ(have.size(), want.size()) << name;
        int changed = 0;
        for (std::size_t m = 0; m < want.size(); ++m)
        {
            EXPECT_EQ(have[m].type, want[m].type);
            EXPECT_EQ(have[m].size, want[m].size);
            ASSERT_EQ(have[m].vars.size(), want[m].vars.size());
            for (std::size_t i = 0; i < want[m].vars.size(); ++i)
            {
                const DecodedVar& w = want[m].vars[i];
                const DecodedVar& h = have[m].vars[i];
                const std::string var_name = names[m].vars[i].name;
                EXPECT_EQ(h.name, w.name) << var_name;
                EXPECT_EQ(h.type, w.type) << var_name;
                ASSERT_EQ(h.value.size(), w.value.size()) << var_name;
                if (h.value == w.value)
                    continue;
                ++changed;
                auto ref = native.find(var_name);
                ASSERT_NE(ref, native.end()) << var_name << " is not in " << reference;
                EXPECT_EQ(h.value, swap_elements(ref->second.value, element_size(h.type, h.value.size())))
                    << name << ": " << var_name << " is not the correctly swapped value";
            }
        }
        EXPECT_GT(changed, 0) << name << " is in EXPECTED_TO_CHANGE but nothing changed";
    }

    // ------------------------------------------------------------------

    const std::set<std::string> needs_python = {
        "ascii_stdio",
        "python_statement",
        "python_syntax_error",
        "python_exception_stops_batch",
    };
    const std::set<std::string> writes_memory = { "ascii_var_set" };
    const std::set<std::string> needs_udunits = { "ascii_units_on_add", "ascii_var_units" };

    class GoldenReplay : public ::testing::TestWithParam<GoldenCase>
    {
    };

} // namespace

TEST_P(GoldenReplay, MatchesTheCapture)
{
    const GoldenCase& gc = GetParam();
    const std::string name(gc.name);
    const std::vector<Command> parsed = parse_batch(gc.script);

    if (needs_python.count(name))
    {
        // These batches hold a line that only Python can run, so the whole
        // batch goes to Python, as one unit.
        ASSERT_EQ(parsed.size(), 1u);
        EXPECT_TRUE(is_fallback(parsed[0]));
        EXPECT_EQ(std::get<cmd::Fallback>(parsed[0]).text, gc.script);
        return;
    }
    for (const Command& c : parsed)
        ASSERT_FALSE(is_fallback(c)) << name << ": every line should be typed";
    if (writes_memory.count(name))
        GTEST_SKIP() << "var_set writes SIM memory; the session tests cover it";

    bool real_units = false;
    auto units      = make_converter(&real_units);
    if (needs_udunits.count(name) && !real_units)
        GTEST_SKIP() << "built without UDUNITS";

    const std::string got = run_script(gc.script, *units);
    if (gc.expected_to_change)
    {
        check_changed_byteswap_case(name, got);
        return;
    }
    const std::string want = golden(name);
    EXPECT_EQ(got.size(), want.size());
    if (got != want)
    {
        std::size_t i = 0;
        while (i < got.size() && i < want.size() && got[i] == want[i])
            ++i;
        ADD_FAILURE() << name << ": first difference at byte " << i << "\n  want: "
                      << ::testing::PrintToString(want.substr(i > 40 ? i - 40 : 0, 120)) << "\n  got:  "
                      << ::testing::PrintToString(got.substr(i > 40 ? i - 40 : 0, 120));
    }
}

INSTANTIATE_TEST_SUITE_P(Conformance, GoldenReplay, ::testing::ValuesIn(golden_cases),
                         [](const ::testing::TestParamInfo<GoldenCase>& info) { return std::string(info.param.name); });

TEST(GoldenReplayCoverage, EveryCaseHasAGolden)
{
    for (const GoldenCase& gc : golden_cases)
        golden(gc.name);
    EXPECT_GE(sizeof golden_cases / sizeof golden_cases[0], 80u);
}
