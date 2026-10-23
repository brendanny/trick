#include "trick/vs/CommandParser.hh"

#include <climits>
#include <cmath>
#include <cstring>

#include <gtest/gtest.h>

using namespace Trick::vs;

namespace
{
    template <class T> T as(const std::string& line)
    {
        Command c = parse_line(line);
        if (!std::holds_alternative<T>(c))
        {
            ADD_FAILURE() << "line: " << line << "\n parsed as: "
                          << (is_fallback(c) ? std::string("Fallback") : std::string(command_name(c)));
            return T {};
        }
        return std::get<T>(c);
    }

    void expect_fallback(const std::string& line)
    {
        Command c = parse_line(line);
        ASSERT_TRUE(is_fallback(c)) << "line: " << line << "\n parsed as: " << command_name(c);
        EXPECT_EQ(std::get<cmd::Fallback>(c).text, line);
    }
} // namespace

// ---------------------------------------------------------------------------
// The forms that the Java (trick_source/java) and Python
// (share/trick/pymods/trick/variable_server.py) clients send.
// ---------------------------------------------------------------------------

TEST(CommandParserClients, VarAdd)
{
    auto a = as<cmd::VarAdd>("trick.var_add(\"trick_sys.sched.time_tic_value\")");
    EXPECT_EQ(a.name, "trick_sys.sched.time_tic_value");
    EXPECT_FALSE(a.units);

    // variable_server.py: 'trick.var_add("{0}"{1})' with ', "{units}"'
    auto b = as<cmd::VarAdd>("trick.var_add(\"ball.obj.state.pos[0]\", \"ft\")");
    EXPECT_EQ(b.name, "ball.obj.state.pos[0]");
    ASSERT_TRUE(b.units);
    EXPECT_EQ(*b.units, "ft");

    // MTV sends ';' after each call.
    auto c = as<cmd::VarAdd>("trick.var_add(\"trick_ip.mtv.mtv_list[0][0].active\"); ");
    EXPECT_EQ(c.name, "trick_ip.mtv.mtv_list[0][0].active");
}

TEST(CommandParserClients, JavaBatchWithSpacesBeforeNewlines)
{
    auto cmds = parse_batch("trick.var_add(\"trick_cmd_args.cmd_args.run_dir\") \n"
                            "trick.var_add(\"trick_sys.sched.mode\") \n"
                            "trick.var_send() \n"
                            "trick.var_clear() \n");
    ASSERT_EQ(cmds.size(), 4u);
    EXPECT_EQ(std::get<cmd::VarAdd>(cmds[0]).name, "trick_cmd_args.cmd_args.run_dir");
    EXPECT_EQ(std::get<cmd::VarAdd>(cmds[1]).name, "trick_sys.sched.mode");
    EXPECT_TRUE(std::holds_alternative<cmd::VarSend>(cmds[2]));
    EXPECT_TRUE(std::holds_alternative<cmd::VarClear>(cmds[3]));
}

TEST(CommandParserClients, MtvSemicolonSeparatedCalls)
{
    auto cmds = parse_batch("trick.var_add(\"a.enabled\"); trick.var_add(\"a.ran_count\"); trick.var_send(); "
                            "trick.var_clear();");
    ASSERT_EQ(cmds.size(), 4u);
    EXPECT_EQ(std::get<cmd::VarAdd>(cmds[1]).name, "a.ran_count");
    EXPECT_TRUE(std::holds_alternative<cmd::VarClear>(cmds[3]));
    // parse_line returns one command, so several statements are a Fallback there.
    expect_fallback("trick.var_send(); trick.var_clear()");
}

TEST(CommandParserClients, ZeroArgumentCommands)
{
    EXPECT_TRUE(std::holds_alternative<cmd::VarSend>(parse_line("trick.var_send()")));
    EXPECT_TRUE(std::holds_alternative<cmd::VarClear>(parse_line("trick.var_clear()")));
    EXPECT_TRUE(std::holds_alternative<cmd::VarPause>(parse_line("trick.var_pause()")));
    EXPECT_TRUE(std::holds_alternative<cmd::VarUnpause>(parse_line("trick.var_unpause()")));
    EXPECT_TRUE(std::holds_alternative<cmd::VarExit>(parse_line("trick.var_exit()")));
    EXPECT_TRUE(std::holds_alternative<cmd::VarAscii>(parse_line("trick.var_ascii()")));
    EXPECT_TRUE(std::holds_alternative<cmd::VarBinary>(parse_line("trick.var_binary()")));
    EXPECT_TRUE(std::holds_alternative<cmd::VarBinaryNoNames>(parse_line("trick.var_binary_nonames()")));
    EXPECT_TRUE(std::holds_alternative<cmd::VarSendListSize>(parse_line("trick.var_send_list_size()")));
    EXPECT_TRUE(std::holds_alternative<cmd::SendSieResource>(parse_line("trick.send_sie_resource()")));
    EXPECT_TRUE(std::holds_alternative<cmd::SendSieClass>(parse_line("trick.send_sie_class()")));
    EXPECT_TRUE(std::holds_alternative<cmd::SendSieEnum>(parse_line("trick.send_sie_enum()")));
    EXPECT_TRUE(
        std::holds_alternative<cmd::SendSieTopLevelObjects>(parse_line("trick.send_sie_top_level_objects()")));
    EXPECT_TRUE(as<cmd::VarServerLog>("trick.var_server_log_on()").on);
    EXPECT_FALSE(as<cmd::VarServerLog>("trick.var_server_log_off()").on);
}

TEST(CommandParserClients, VarCycle)
{
    EXPECT_DOUBLE_EQ(as<cmd::VarCycle>("trick.var_cycle(0.25)").seconds, 0.25);
    EXPECT_DOUBLE_EQ(as<cmd::VarCycle>("trick.var_cycle(0.01)").seconds, 0.01);
    // Java: "trick.var_cycle(" + period + ")" with an int or a double
    EXPECT_DOUBLE_EQ(as<cmd::VarCycle>("trick.var_cycle(1)").seconds, 1.0);
    EXPECT_DOUBLE_EQ(as<cmd::VarCycle>("trick.var_cycle(1.0E-4)").seconds, 1.0e-4);
}

TEST(CommandParserClients, BoolsAsPythonWritesThem)
{
    // variable_server.py: format(bool(x)) gives True / False.
    EXPECT_TRUE(as<cmd::VarValidateAddress>("trick.var_validate_address(True)").on);
    EXPECT_FALSE(as<cmd::VarValidateAddress>("trick.var_validate_address(False)").on);
    EXPECT_EQ(as<cmd::VarSetWriteMode>("trick.var_set_write_mode(True)").mode, 1);
    EXPECT_EQ(as<cmd::VarSetWriteMode>("trick.var_set_write_mode(False)").mode, 0);
}

TEST(CommandParserClients, IntSettings)
{
    EXPECT_EQ(as<cmd::VarDebug>("trick.var_debug(3)").level, 3);
    EXPECT_EQ(as<cmd::VarSync>("trick.var_sync(1)").mode, 1);
    EXPECT_EQ(as<cmd::VarSetCopyMode>("trick.var_set_copy_mode(2)").mode, 2);
    EXPECT_EQ(as<cmd::VarSetFrameMultiple>("trick.var_set_frame_multiple(4)").multiple, 4u);
    EXPECT_EQ(as<cmd::VarSetFrameOffset>("trick.var_set_frame_offset(1)").offset, 1u);
    EXPECT_EQ(as<cmd::VarSetFreezeFrameMultiple>("trick.var_set_freeze_frame_multiple(2)").multiple, 2u);
    EXPECT_EQ(as<cmd::VarSetFreezeFrameOffset>("trick.var_set_freeze_frame_offset(0)").offset, 0u);
    EXPECT_TRUE(as<cmd::VarSetSendStdio>("trick.var_set_send_stdio(1)").on);
    EXPECT_TRUE(as<cmd::VarByteswap>("trick.var_byteswap(True)").on);
}

TEST(CommandParserClients, StringCommands)
{
    EXPECT_EQ(as<cmd::VarRemove>("trick.var_remove(\"a.b\")").name, "a.b");
    EXPECT_EQ(as<cmd::VarExists>("trick.var_exists(\"trick_variable_server_handshake\")").name,
              "trick_variable_server_handshake");
    EXPECT_EQ(as<cmd::VarExists>("trick.var_exists(\"trick_message.mdevice.port\")").name,
              "trick_message.mdevice.port");
    EXPECT_EQ(as<cmd::VarGetStlSize>("trick.var_get_stl_size(\"a.vec\")").name, "a.vec");
    EXPECT_EQ(as<cmd::VarSetClientTag>("trick.var_set_client_tag(\"SimControl\")").tag, "SimControl");
    EXPECT_EQ(as<cmd::SendFile>("trick.send_file(\"S_sie.resource\")").path, "S_sie.resource");
    auto u = as<cmd::VarUnits>("trick.var_units(\"a.b\", \"m/s\")");
    EXPECT_EQ(u.name, "a.b");
    EXPECT_EQ(u.units, "m/s");
    auto w = as<cmd::VarWriteStdio>("trick.var_write_stdio(2, \"oops\\n\")");
    EXPECT_EQ(w.stream, 2);
    EXPECT_EQ(w.text, "oops\n");
}

TEST(CommandParserClients, VarSendOnce)
{
    auto a = as<cmd::VarSendOnce>("trick.var_send_once(\"a.x,a.y\", 2)");
    EXPECT_EQ(a.names, "a.x,a.y");
    ASSERT_TRUE(a.count);
    EXPECT_EQ(*a.count, 2);
    auto b = as<cmd::VarSendOnce>("trick.var_send_once(\"a.x\")");
    EXPECT_FALSE(b.count);
}

TEST(CommandParserClients, VarSetFromPythonClient)
{
    // 'trick.var_set("{0}", {1}{2})'.format(name, value, ', "{units}"')
    auto f = as<cmd::VarSet>("trick.var_set(\"a.d\", 1.5)");
    EXPECT_EQ(f.name, "a.d");
    EXPECT_EQ(std::get<double>(f.value), 1.5);
    EXPECT_FALSE(f.units);

    auto i = as<cmd::VarSet>("trick.var_set(\"a.i\", -7, \"m\")");
    EXPECT_EQ(std::get<long long>(i.value), -7);
    ASSERT_TRUE(i.units);
    EXPECT_EQ(*i.units, "m");

    auto s = as<cmd::VarSet>("trick.var_set(\"a.s\", \"text\")");
    EXPECT_EQ(std::get<std::string>(s.value), "text");

    auto n = as<cmd::VarSet>("trick.var_set(\"a.p\", None)");
    EXPECT_TRUE(std::holds_alternative<cmd::NoneValue>(n.value));

    // SWIG picks the long long overload for a bool.
    auto b = as<cmd::VarSet>("trick.var_set(\"a.b\", True)");
    EXPECT_EQ(std::get<long long>(b.value), 1);

    // The units argument may be None (NULL).
    auto un = as<cmd::VarSet>("trick.var_set(\"a.d\", 2.0, None)");
    EXPECT_FALSE(un.units);
}

TEST(CommandParserClients, OtherPathsStayInPython)
{
    // Old Java clients use trick.sim_services.*; Python decides what that is.
    expect_fallback("trick.sim_services.var_add(\"a.b\")");
    expect_fallback("trick.var_allow_connections()");
    expect_fallback("trick.mtv_send_event_data();");
}

// ---------------------------------------------------------------------------
// Literals
// ---------------------------------------------------------------------------

TEST(CommandParserLiterals, StringEscapes)
{
    EXPECT_EQ(as<cmd::VarRemove>(R"(trick.var_remove("a\\b\'\"\a\b\f\n\r\t\v"))").name,
              std::string("a\\b'\"\a\b\f\n\r\t\v"));
    EXPECT_EQ(as<cmd::VarRemove>(R"(trick.var_remove('\101\x42C\U00000044'))").name, "ABCD");
    // Non-ASCII escapes are code points, stored as UTF-8.
    EXPECT_EQ(as<cmd::VarRemove>(R"(trick.var_remove("\xe9é\U0001F600"))").name,
              "\xC3\xA9\xC3\xA9\xF0\x9F\x98\x80");
    // An unknown escape keeps the backslash.
    EXPECT_EQ(as<cmd::VarRemove>(R"(trick.var_remove("a\qb\["))").name, "a\\qb\\[");
    // Raw UTF-8 passes through.
    EXPECT_EQ(as<cmd::VarRemove>("trick.var_remove(\"\xC3\xA9\")").name, "\xC3\xA9");
    // u prefix is a plain str.
    EXPECT_EQ(as<cmd::VarRemove>("trick.var_remove(u'x')").name, "x");
    EXPECT_EQ(as<cmd::VarRemove>("trick.var_remove(U\"x\")").name, "x");
    // Quotes of the other kind need no escape.
    EXPECT_EQ(as<cmd::VarRemove>("trick.var_remove('a\"b')").name, "a\"b");
}

TEST(CommandParserLiterals, StringsThatStayInPython)
{
    expect_fallback("trick.var_remove(r\"a\\b\")");    // raw
    expect_fallback("trick.var_remove(b\"a\")");       // bytes
    expect_fallback("trick.var_remove(f\"{x}\")");     // f-string
    expect_fallback("trick.var_remove(\"\"\"a\"\"\")"); // triple quotes
    expect_fallback("trick.var_remove('''a''')");
    expect_fallback("trick.var_remove(\"a\" \"b\")");  // concatenation
    expect_fallback("trick.var_remove(\"a\\N{BULLET}\")");
    expect_fallback("trick.var_remove(\"a\\x4\")");        // bad \x
    expect_fallback("trick.var_remove(\"a\\uD800\")");     // surrogate
    expect_fallback("trick.var_remove(\"a\\U00110000\")"); // past U+10FFFF
    expect_fallback("trick.var_remove(\"a\\0\")");         // NUL
    expect_fallback("trick.var_remove(\"a");               // unterminated
    expect_fallback("trick.var_remove(\"a\\");
    expect_fallback("trick.var_remove(\"\xff\")");         // not UTF-8
    expect_fallback("trick.var_remove(\"\xC0\x80\")");     // overlong
    expect_fallback("trick.var_remove(\"\xED\xA0\x80\")"); // encoded surrogate
}

TEST(CommandParserLiterals, Integers)
{
    EXPECT_EQ(as<cmd::VarDebug>("trick.var_debug(0)").level, 0);
    EXPECT_EQ(as<cmd::VarDebug>("trick.var_debug(000)").level, 0);
    EXPECT_EQ(as<cmd::VarDebug>("trick.var_debug(0x1F)").level, 31);
    EXPECT_EQ(as<cmd::VarDebug>("trick.var_debug(0X_1f)").level, 31);
    EXPECT_EQ(as<cmd::VarDebug>("trick.var_debug(0o17)").level, 15);
    EXPECT_EQ(as<cmd::VarDebug>("trick.var_debug(0b101)").level, 5);
    EXPECT_EQ(as<cmd::VarDebug>("trick.var_debug(1_000)").level, 1000);
    EXPECT_EQ(as<cmd::VarDebug>("trick.var_debug(-3)").level, -3);
    EXPECT_EQ(as<cmd::VarDebug>("trick.var_debug(- -+3)").level, 3);
    EXPECT_EQ(as<cmd::VarSet>("trick.var_set(\"a\", 9223372036854775807)").value,
              cmd::SetValue(static_cast<long long>(LLONG_MAX)));
    EXPECT_EQ(as<cmd::VarSet>("trick.var_set(\"a\", -9223372036854775808)").value,
              cmd::SetValue(static_cast<long long>(LLONG_MIN)));
}

TEST(CommandParserLiterals, IntegersThatStayInPython)
{
    expect_fallback("trick.var_debug(01)");                  // SyntaxError in Python 3
    expect_fallback("trick.var_debug(1__0)");
    expect_fallback("trick.var_debug(1_)");
    expect_fallback("trick.var_debug(0x)");
    expect_fallback("trick.var_debug(0b2)");
    expect_fallback("trick.var_debug(1j)");                  // complex
    expect_fallback("trick.var_debug(1L)");
    expect_fallback("trick.var_set(\"a\", 9223372036854775808)"); // past int64: the double overload
    expect_fallback("trick.var_set(\"a\", -9223372036854775809)");
    expect_fallback("trick.var_debug(-True)");               // an expression
    expect_fallback("trick.var_debug(1+1)");
}

TEST(CommandParserLiterals, Floats)
{
    EXPECT_DOUBLE_EQ(as<cmd::VarCycle>("trick.var_cycle(.5)").seconds, 0.5);
    EXPECT_DOUBLE_EQ(as<cmd::VarCycle>("trick.var_cycle(5.)").seconds, 5.0);
    EXPECT_DOUBLE_EQ(as<cmd::VarCycle>("trick.var_cycle(1e-3)").seconds, 1e-3);
    EXPECT_DOUBLE_EQ(as<cmd::VarCycle>("trick.var_cycle(1_0.2_5)").seconds, 10.25);
    EXPECT_DOUBLE_EQ(as<cmd::VarCycle>("trick.var_cycle(00.5)").seconds, 0.5);
    EXPECT_DOUBLE_EQ(as<cmd::VarCycle>("trick.var_cycle(-2.5E+1)").seconds, -25.0);
    EXPECT_TRUE(std::isinf(as<cmd::VarCycle>("trick.var_cycle(1e999)").seconds));
    EXPECT_EQ(as<cmd::VarCycle>("trick.var_cycle(1e-999)").seconds, 0.0);
    expect_fallback("trick.var_cycle(1.2.3)");
    expect_fallback("trick.var_cycle(1e)");
    expect_fallback("trick.var_cycle(1._5)");
    expect_fallback("trick.var_cycle(.)");
    expect_fallback("trick.var_cycle(float('nan'))");
}

TEST(CommandParserLiterals, FloatsUseTheCLocale)
{
    const char* old = std::setlocale(LC_NUMERIC, nullptr);
    const std::string saved = old ? old : "C";
    if (std::setlocale(LC_NUMERIC, "de_DE.UTF-8") == nullptr)
        GTEST_SKIP() << "de_DE.UTF-8 is not installed";
    const double v = as<cmd::VarCycle>("trick.var_cycle(0.25)").seconds;
    std::setlocale(LC_NUMERIC, saved.c_str());
    EXPECT_DOUBLE_EQ(v, 0.25);
}

// ---------------------------------------------------------------------------
// Statement shape
// ---------------------------------------------------------------------------

TEST(CommandParserShape, Spacing)
{
    EXPECT_EQ(as<cmd::VarAdd>("trick . var_add ( \"a\" , \"m\" , )").units, std::optional<std::string>("m"));
    EXPECT_EQ(as<cmd::VarAdd>("trick.var_add(\"a\",)").name, "a");
    EXPECT_EQ(as<cmd::VarAdd>("trick.var_add(\"a\")\t# comment ) junk").name, "a");
    EXPECT_EQ(as<cmd::VarAdd>("trick.var_add(\"a#b\")").name, "a#b");
    EXPECT_EQ(as<cmd::VarAdd>("trick.var_add(\"a\");").name, "a");
}

TEST(CommandParserShape, NotASingleCall)
{
    expect_fallback("");
    expect_fallback(" trick.var_send()");           // indented
    expect_fallback("trick.var_send");
    expect_fallback("trick.var_send()()");
    expect_fallback("trick.var_send() trick.var_send()");
    expect_fallback("trick.var_send();;");
    expect_fallback("x = trick.var_send()");
    expect_fallback("trick.var_add(name)");          // a variable
    expect_fallback("trick.var_add(\"a\", units=\"m\")"); // keyword
    expect_fallback("trick.var_add(*args)");
    expect_fallback("trick.var_add(\"a\",,)");
    expect_fallback("trick.var_add(,)");
    expect_fallback("trickvar.var_add(\"a\")");
    expect_fallback("print(\"hello\")");
    expect_fallback("trick.var_send() \\");          // line continuation
    expect_fallback("trick.var_send() # a\rtrick.var_exit()"); // '\r' is a line break
    expect_fallback("trick.var_send() # a\ntrick.var_exit()");
    expect_fallback("trick.var_send() # \xff");     // not UTF-8, even in a comment
    expect_fallback(std::string("trick.var_send()\0x", 18));
}

// ---------------------------------------------------------------------------
// Argument conversion: SWIG overload checks and Trick's scalar typemaps
// ---------------------------------------------------------------------------

TEST(CommandParserArguments, ArgumentCounts)
{
    expect_fallback("trick.var_send(1)");
    expect_fallback("trick.var_add()");
    expect_fallback("trick.var_add(\"a\", \"b\", \"c\")");
    expect_fallback("trick.var_units(\"a\")");
    expect_fallback("trick.var_cycle()");
    expect_fallback("trick.var_cycle(1, 2)");
    expect_fallback("trick.var_set(\"a\")");
    expect_fallback("trick.var_set(\"a\", 1, \"m\", 4)");
    expect_fallback("trick.var_write_stdio(1)");
}

TEST(CommandParserArguments, StdStringTakesOnlyStr)
{
    expect_fallback("trick.var_add(None)");
    expect_fallback("trick.var_add(1)");
    expect_fallback("trick.var_add(\"a\", None)");
    expect_fallback("trick.var_add(\"a\", 1)");
    expect_fallback("trick.var_units(\"a\", True)");
    expect_fallback("trick.var_set_client_tag(5)");
    expect_fallback("trick.var_write_stdio(1, 2)");
    expect_fallback("trick.var_set(None, 1)");
}

TEST(CommandParserArguments, SendOnceCountIsAStrictInt)
{
    EXPECT_EQ(as<cmd::VarSendOnce>("trick.var_send_once(\"a\", True)").count, std::optional<int>(1));
    expect_fallback("trick.var_send_once(\"a\", 2.0)");
    expect_fallback("trick.var_send_once(\"a\", \"2\")");
    expect_fallback("trick.var_send_once(\"a\", 2147483648)");
    EXPECT_EQ(as<cmd::VarSendOnce>("trick.var_send_once(\"a\", -2147483648)").count,
              std::optional<int>(INT_MIN));
}

TEST(CommandParserArguments, ScalarTypemapFloatToInt)
{
    // (int)PyFloat_AsDouble truncates toward zero.
    EXPECT_EQ(as<cmd::VarDebug>("trick.var_debug(2.9)").level, 2);
    EXPECT_EQ(as<cmd::VarDebug>("trick.var_debug(-2.9)").level, -2);
    EXPECT_EQ(as<cmd::VarSetFrameMultiple>("trick.var_set_frame_multiple(-0.5)").multiple, 0u);
    // Out of range or not finite is undefined in C: leave it to Python.
    expect_fallback("trick.var_debug(1e10)");
    expect_fallback("trick.var_debug(1e999)");
    expect_fallback("trick.var_set_frame_multiple(-1.0)");
}

TEST(CommandParserArguments, ScalarTypemapIntWraps)
{
    // (int)PyInt_AsLong and (unsigned int)PyInt_AsLong
    EXPECT_EQ(as<cmd::VarDebug>("trick.var_debug(4294967297)").level, 1);
    EXPECT_EQ(as<cmd::VarSetFrameMultiple>("trick.var_set_frame_multiple(-1)").multiple, 4294967295u);
    EXPECT_EQ(as<cmd::VarSetFrameOffset>("trick.var_set_frame_offset(4294967296)").offset, 0u);
}

TEST(CommandParserArguments, ScalarTypemapOneCharacterString)
{
    EXPECT_EQ(as<cmd::VarDebug>("trick.var_debug(\"A\")").level, 65);
    EXPECT_DOUBLE_EQ(as<cmd::VarCycle>("trick.var_cycle('0')").seconds, 48.0);
    // The first UTF-8 byte, as a C char.
    EXPECT_EQ(as<cmd::VarDebug>("trick.var_debug(\"\xC3\xA9\")").level, static_cast<int>(static_cast<char>(0xC3)));
    // Any other length leaves the C value unset: leave it to Python.
    expect_fallback("trick.var_debug(\"\")");
    expect_fallback("trick.var_debug(\"12\")");
    expect_fallback("trick.var_debug(None)");
}

TEST(CommandParserArguments, BoolTypemapRejectsStrings)
{
    EXPECT_TRUE(as<cmd::VarByteswap>("trick.var_byteswap(1)").on);
    EXPECT_FALSE(as<cmd::VarByteswap>("trick.var_byteswap(0.0)").on);
    EXPECT_TRUE(as<cmd::VarByteswap>("trick.var_byteswap(0.5)").on);
    expect_fallback("trick.var_byteswap(\"1\")");
    EXPECT_TRUE(as<cmd::VarSendIpErrors>("trick.var_send_ip_errors(True)").on);
    EXPECT_FALSE(as<cmd::VarSendIpErrors>("trick.var_send_ip_errors(0)").on);
    expect_fallback("trick.var_send_ip_errors(\"1\")");
    expect_fallback("trick.var_byteswap(None)");
}

TEST(CommandParserArguments, VarSetUnits)
{
    expect_fallback("trick.var_set(\"a\", 1, 2)");
    expect_fallback("trick.var_set(\"a\", 1, True)");
    expect_fallback("trick.var_set(\"a\", \"x\\0y\")");
}

// ---------------------------------------------------------------------------
// Batches
// ---------------------------------------------------------------------------

TEST(CommandParserBatch, SkipsBlankAndCommentLines)
{
    auto cmds = parse_batch("\n# setup\n  \ntrick.var_send()\n   # indented comment\n\r\n");
    ASSERT_EQ(cmds.size(), 1u);
    EXPECT_TRUE(std::holds_alternative<cmd::VarSend>(cmds[0]));
    EXPECT_TRUE(parse_batch("").empty());
    EXPECT_TRUE(parse_batch("\n\n").empty());
}

TEST(CommandParserBatch, CrLfLineEnds)
{
    auto cmds = parse_batch("trick.var_add(\"a\")\r\ntrick.var_send()\r\n");
    ASSERT_EQ(cmds.size(), 2u);
}

TEST(CommandParserBatch, OneUntypedLineSendsTheWholeBatchToPython)
{
    const std::string text = "trick.var_add(\"a\")\nprint(1)\ntrick.var_send()\n";
    auto cmds              = parse_batch(text);
    ASSERT_EQ(cmds.size(), 1u);
    ASSERT_TRUE(is_fallback(cmds[0]));
    EXPECT_EQ(std::get<cmd::Fallback>(cmds[0]).text, text);
}

TEST(CommandParserBatch, SourcePythonWouldReadDifferently)
{
    for (const std::string& text : {
             std::string("trick.var_send()\n# \xff\n"),                // not UTF-8 in a comment
             std::string("# -*- coding: latin-1 -*-\ntrick.var_send()\n"), // encoding declaration
             std::string("\n# vim: set fileencoding=latin-1 :\ntrick.var_send()\n"),
             std::string("trick.var_send()\n# a\rtrick.var_exit()\n"), // '\r' is a line break
             std::string("trick.var_send()\n\0trick.var_exit()\n", 35),
         })
    {
        auto cmds = parse_batch(text);
        ASSERT_EQ(cmds.size(), 1u);
        EXPECT_TRUE(is_fallback(cmds[0]));
        EXPECT_EQ(std::get<cmd::Fallback>(cmds[0]).text, text);
    }
    // An encoding declaration after line two is only a comment.
    EXPECT_EQ(parse_batch("trick.var_send()\n\n# coding: latin-1\n").size(), 1u);
    EXPECT_FALSE(is_fallback(parse_batch("trick.var_send()\n\n# coding: latin-1\n")[0]));
}

// ---------------------------------------------------------------------------
// to_python
// ---------------------------------------------------------------------------

TEST(CommandParserToPython, RoundTrips)
{
    const std::vector<Command> commands = {
        cmd::VarAdd { "a.b[0]", std::nullopt },
        cmd::VarAdd { "a\"\\\n\t\x01\xC3\xA9", std::string("m/s") },
        cmd::VarRemove { "x" },
        cmd::VarUnits { "x", "ft" },
        cmd::VarClear {},
        cmd::VarSend {},
        cmd::VarSendOnce { "a,b", 2 },
        cmd::VarSendOnce { "a", std::nullopt },
        cmd::VarExists { "e" },
        cmd::VarGetStlSize { "v" },
        cmd::VarSendListSize {},
        cmd::VarCycle { 0.1 },
        cmd::VarCycle { -0.0 },
        cmd::VarCycle { 1e300 },
        cmd::VarCycle { HUGE_VAL },
        cmd::VarCycle { 5e-324 },
        cmd::VarPause {},
        cmd::VarUnpause {},
        cmd::VarSetCopyMode { -1 },
        cmd::VarSetWriteMode { 1 },
        cmd::VarSync { 2 },
        cmd::VarSetFrameMultiple { 4294967295u },
        cmd::VarSetFrameOffset { 3 },
        cmd::VarSetFreezeFrameMultiple { 2 },
        cmd::VarSetFreezeFrameOffset { 1 },
        cmd::VarAscii {},
        cmd::VarBinary {},
        cmd::VarBinaryNoNames {},
        cmd::VarByteswap { true },
        cmd::VarValidateAddress { false },
        cmd::VarDebug { INT_MIN },
        cmd::VarSetClientTag { "tag" },
        cmd::VarSetSendStdio { true },
        cmd::VarWriteStdio { 2, "x\n" },
        cmd::VarServerLog { true },
        cmd::VarServerLog { false },
        cmd::VarExit {},
        cmd::SendSieResource {},
        cmd::SendSieClass {},
        cmd::SendSieEnum {},
        cmd::SendSieTopLevelObjects {},
        cmd::SendFile { "f.txt" },
        cmd::VarSet { "a", 1.25, std::nullopt },
        cmd::VarSet { "a", 3.0, std::string("m") },
        cmd::VarSet { "a", static_cast<long long>(LLONG_MIN), std::nullopt },
        cmd::VarSet { "a", std::string("text"), std::nullopt },
        cmd::VarSet { "a", cmd::NoneValue {}, std::string("") },
    };
    for (const Command& c : commands)
    {
        const std::string py = to_python(c);
        const Command back   = parse_line(py);
        ASSERT_FALSE(is_fallback(back)) << py;
        EXPECT_EQ(to_python(back), py);
        EXPECT_EQ(back.index(), c.index()) << py;
    }
    EXPECT_EQ(to_python(cmd::VarAdd { "a", std::string("m") }), "trick.var_add(\"a\", \"m\")");
    EXPECT_EQ(to_python(cmd::VarSend {}), "trick.var_send()");
    EXPECT_EQ(to_python(cmd::VarCycle { 0.25 }), "trick.var_cycle(0.25)");
    EXPECT_EQ(to_python(cmd::Fallback { "print(1)" }), "print(1)");
}

// ---------------------------------------------------------------------------
// split_send_once_names: the old server's std::getline(ss, name, ',')
// ---------------------------------------------------------------------------

TEST(CommandParserSendOnce, SplitsLikeGetline)
{
    using V = std::vector<std::string>;
    EXPECT_EQ(split_send_once_names("a,b"), (V { "a", "b" }));
    EXPECT_EQ(split_send_once_names("a,b,"), (V { "a", "b" }));
    EXPECT_EQ(split_send_once_names(",a"), (V { "", "a" }));
    EXPECT_EQ(split_send_once_names("a,,b"), (V { "a", "", "b" }));
    EXPECT_EQ(split_send_once_names(" a , b"), (V { " a ", " b" }));
    EXPECT_EQ(split_send_once_names(","), (V { "" }));
    EXPECT_EQ(split_send_once_names(""), V {});
}
