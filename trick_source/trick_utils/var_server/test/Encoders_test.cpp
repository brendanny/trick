#include "trick/vs/AsciiEncoder.hh"
#include "trick/vs/BinaryEncoder.hh"
#include "trick/vs/FixedReply.hh"
#include "trick/vs/Packetizer.hh"
#include "trick/vs/Units.hh"
#include "trick/vs/testing/Fakes.hh"

#include <clocale>
#include <cmath>
#include <cstring>
#include <limits>
#include <vector>

#include <gtest/gtest.h>

using namespace Trick::vs;
using namespace Trick::vs::testing;

namespace
{
    template <class T> std::string ascii(WireType type, std::vector<T> values, const Conversion* c = nullptr,
                                         std::string_view units = {})
    {
        std::string out;
        append_ascii_value(out, FieldDesc::array(type, sizeof(T), static_cast<uint32_t>(values.size())),
                           reinterpret_cast<const unsigned char*>(values.data()), c, units);
        return out;
    }

    template <class T> std::string ascii1(WireType type, T value, const Conversion* c = nullptr)
    {
        return ascii<T>(type, { value }, c);
    }

    std::string narrow(const std::string& bytes)
    {
        std::string out;
        append_escaped_narrow(out, reinterpret_cast<const unsigned char*>(bytes.data()), bytes.size());
        return out;
    }

    std::string wide(const std::vector<uint32_t>& w)
    {
        std::string out;
        append_escaped_wide(out, reinterpret_cast<const unsigned char*>(w.data()), w.size(), 4);
        return out;
    }

    std::string hex(const std::string& s)
    {
        static const char* d = "0123456789abcdef";
        std::string out;
        for (unsigned char c : s)
        {
            out += d[c >> 4];
            out += d[c & 15];
        }
        return out;
    }

    Bitfield bf(uint16_t start, uint16_t width)
    {
        Bitfield b;
        b.start = start;
        b.width = width;
        return b;
    }
} // namespace

// ---------------------------------------------------------------------------
// ASCII numbers
// ---------------------------------------------------------------------------

TEST(AsciiEncoder, Integers)
{
    EXPECT_EQ(ascii1<char>(WireType::Character, 'A'), "65");
    EXPECT_EQ(ascii1<signed char>(WireType::Character, -5), "-5");
    EXPECT_EQ(ascii1<unsigned char>(WireType::UnsignedCharacter, 200), "200");
    EXPECT_EQ(ascii1<short>(WireType::Short, -1234), "-1234");
    EXPECT_EQ(ascii1<unsigned short>(WireType::UnsignedShort, 54321), "54321");
    EXPECT_EQ(ascii1<int>(WireType::Integer, std::numeric_limits<int>::min()), "-2147483648");
    EXPECT_EQ(ascii1<unsigned>(WireType::UnsignedInteger, 4000000000u), "4000000000");
    EXPECT_EQ(ascii1<long long>(WireType::Long, -1234567890123LL), "-1234567890123");
    EXPECT_EQ(ascii1<int32_t>(WireType::Long, -7), "-7"); // a 4-byte long
    EXPECT_EQ(ascii1<unsigned long long>(WireType::UnsignedLongLong, std::numeric_limits<unsigned long long>::max()),
              "18446744073709551615");
    EXPECT_EQ(ascii1<long long>(WireType::LongLong, std::numeric_limits<long long>::min()), "-9223372036854775808");
    EXPECT_EQ(ascii1<uint8_t>(WireType::Boolean, 1), "1");
    EXPECT_EQ(ascii1<int32_t>(WireType::WideCharacter, L'W'), "87");
}

TEST(AsciiEncoder, EnumsUseTheirRealSize)
{
    // Phase 0 defect: the old writer read 4 bytes for a 2-byte enum.
    EXPECT_EQ(ascii1<int16_t>(WireType::Enumerated, -2), "-2");
    EXPECT_EQ(ascii1<int8_t>(WireType::Enumerated, 7), "7");
    EXPECT_EQ(ascii1<int32_t>(WireType::Enumerated, 2), "2");
    EXPECT_EQ(ascii1<int64_t>(WireType::Enumerated, -5000000000LL), "-5000000000");
}

TEST(AsciiEncoder, FloatingPoint)
{
    EXPECT_EQ(ascii1<double>(WireType::Double, 3.141592653589793), "3.141592653589793");
    EXPECT_EQ(ascii1<double>(WireType::Double, 1.0 / 3.0), "0.3333333333333333");
    EXPECT_EQ(ascii1<double>(WireType::Double, 1e300), "1e+300");
    EXPECT_EQ(ascii1<double>(WireType::Double, 0.0), "0");
    EXPECT_EQ(ascii1<double>(WireType::Double, std::numeric_limits<double>::infinity()), "inf");
    EXPECT_EQ(ascii1<double>(WireType::Double, -std::numeric_limits<double>::infinity()), "-inf");
    EXPECT_EQ(ascii1<double>(WireType::Double, std::numeric_limits<double>::quiet_NaN()), "nan");
    EXPECT_EQ(ascii1<float>(WireType::Float, 1.0f / 3.0f), "0.33333334");
    EXPECT_EQ(ascii1<float>(WireType::Float, 1.5f), "1.5");
}

TEST(AsciiEncoder, FloatingPointUsesTheCLocale)
{
    const char* old         = std::setlocale(LC_NUMERIC, nullptr);
    const std::string saved = old ? old : "C";
    if (std::setlocale(LC_NUMERIC, "de_DE.UTF-8") == nullptr)
        GTEST_SKIP() << "de_DE.UTF-8 is not installed";
    const std::string text = ascii1<double>(WireType::Double, 2.5);
    std::setlocale(LC_NUMERIC, saved.c_str());
    EXPECT_EQ(text, "2.5");
}

TEST(AsciiEncoder, ArraysAreCommaSeparated)
{
    EXPECT_EQ(ascii<int>(WireType::Integer, { 10, 20, 30 }), "10,20,30");
    EXPECT_EQ(ascii<double>(WireType::Double, { 0, 0.5, 1 }), "0,0.5,1");
    EXPECT_EQ(ascii<int>(WireType::Integer, {}), "");
}

TEST(AsciiEncoder, TypesWithNoTextAreEmptyFields)
{
    EXPECT_EQ(ascii<uint64_t>(WireType::Structured, { 1, 2, 3 }), ",,");
    EXPECT_EQ(ascii1<uint64_t>(WireType::VoidPtr, 1), "");
    EXPECT_EQ(ascii1<int32_t>(WireType::BadRef, 0), "BAD_REF");
}

TEST(AsciiEncoder, Conversions)
{
    FakeConversion to_cm(100.0, 0.0);
    EXPECT_EQ(ascii1<double>(WireType::Double, 1.5, &to_cm), "150");
    EXPECT_EQ(ascii1<int>(WireType::Integer, 3, &to_cm), "300");
    EXPECT_EQ(ascii1<float>(WireType::Float, 0.25f, &to_cm), "25");
    EXPECT_EQ(ascii1<short>(WireType::Short, 2, &to_cm), "200");
    // Clamped, where the old C cast was undefined.
    EXPECT_EQ(ascii1<short>(WireType::Short, 1000, &to_cm), "32767");
    EXPECT_EQ(ascii1<unsigned>(WireType::UnsignedInteger, 1u << 30, &to_cm), "4294967295");
    FakeConversion negate(-1.0, 0.0);
    EXPECT_EQ(ascii1<unsigned>(WireType::UnsignedInteger, 5, &negate), "0");
    // With no conversion, 64-bit integers print exactly.
    EXPECT_EQ(ascii1<long long>(WireType::LongLong, 9007199254740993LL), "9007199254740993");
    // A single wchar_t and a bitfield are not converted, as in the old server.
    EXPECT_EQ(ascii1<int32_t>(WireType::WideCharacter, 87, &to_cm), "87");
}

TEST(AsciiEncoder, UnitsSuffix)
{
    EXPECT_EQ(ascii<double>(WireType::Double, { 1.0 }, nullptr, "m"), "1 {m}");
    EXPECT_EQ(ascii<double>(WireType::Double, { 0, 50 }, nullptr, "cm"), "0,50 {cm}");
    FieldDesc d = FieldDesc::scalar(WireType::Double, 8);
    d.units_dashdash = true;
    const double v   = 42;
    std::string out;
    append_ascii_value(out, d, reinterpret_cast<const unsigned char*>(&v), nullptr, "1");
    EXPECT_EQ(out, "42 {--}");
    out.clear();
    append_ascii_value(out, d, reinterpret_cast<const unsigned char*>(&v), nullptr, "");
    EXPECT_EQ(out, "42");
}

// ---------------------------------------------------------------------------
// ASCII text
// ---------------------------------------------------------------------------

TEST(AsciiEncoder, NarrowEscapes)
{
    EXPECT_EQ(narrow("tab\there\nnew \"q\" \\ end"), "tab\\there\\nnew \"q\" \\ end");
    EXPECT_EQ(narrow("\a\b\f\v\r"), "\\a\\b\\f\\v\\n");
    EXPECT_EQ(narrow(std::string("\x01\x7f", 2)), "\\x01\\x7f");
    // Phase 2 change: the old server wrote \xffffffe9.
    EXPECT_EQ(narrow("\xe9"), "\\xe9");
}

TEST(AsciiEncoder, NarrowTextStopsAtNulOrCount)
{
    EXPECT_EQ(narrow(std::string("ab\0cd", 5)), "ab");
    // Phase 0 defect: a char array with no NUL. Only its own bytes are read.
    std::string out;
    const char full[8] = { 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H' };
    append_ascii_value(out, FieldDesc::char_array(8), reinterpret_cast<const unsigned char*>(full), nullptr, "");
    EXPECT_EQ(out, "ABCDEFGH");
}

TEST(AsciiEncoder, WideEscapes)
{
    EXPECT_EQ(wide({ 'w', 'i', 'd', 'e', 0, 'x' }), "wide");
    EXPECT_EQ(wide({ '\'', '"', '?', '\\' }), "\\'\\\"\\?\\\\");
    EXPECT_EQ(wide({ '\a', '\b', '\f', '\n', '\r', '\t', '\v', 1 }), "\\a\\b\\f\\n\\n\\t\\v\\x01");
    EXPECT_EQ(wide({ 0xE9, 0x20AC, 0x1F600 }), "\\xe9\\u20AC\\U0001F600");
    std::string out;
    const uint16_t w16[] = { 'h', 'i', 0x20AC };
    append_escaped_wide(out, reinterpret_cast<const unsigned char*>(w16), 3, 2);
    EXPECT_EQ(out, "hi\\u20AC");
}

// ---------------------------------------------------------------------------
// Bitfields and binary values
// ---------------------------------------------------------------------------

TEST(BinaryEncoder, BitfieldsAsIcgDescribesThem)
{
    // class { unsigned u3:3; unsigned u5:5; int s4:4; int s12:12; } with
    // u3=5, u5=31, s4=-3, s12=1000, on a little-endian host. ICG counts
    // start from the most significant bit.
    const uint32_t word = 5u | (31u << 3) | (13u << 8) | (1000u << 12);
    const auto* p       = reinterpret_cast<const unsigned char*>(&word);
    EXPECT_EQ(extract_bitfield(p, 4, bf(29, 3), false), 5);
    EXPECT_EQ(extract_bitfield(p, 4, bf(24, 5), false), 31);
    EXPECT_EQ(extract_bitfield(p, 4, bf(20, 4), true), -3);
    EXPECT_EQ(extract_bitfield(p, 4, bf(20, 4), false), 13);
    EXPECT_EQ(extract_bitfield(p, 4, bf(8, 12), true), 1000);
    // Whole storage unit
    const uint32_t all = 0xFFFFFFFFu;
    EXPECT_EQ(extract_bitfield(reinterpret_cast<const unsigned char*>(&all), 4, bf(0, 32), true), -1);
    // 1- and 2-byte storage
    const uint8_t b = 0xA0; // top 3 bits 101
    EXPECT_EQ(extract_bitfield(&b, 1, bf(0, 3), false), 5);
    EXPECT_EQ(extract_bitfield(&b, 1, bf(0, 3), true), -3);
    const uint16_t s = 0x0F00;
    EXPECT_EQ(extract_bitfield(reinterpret_cast<const unsigned char*>(&s), 2, bf(4, 4), false), 15);
}

TEST(BinaryEncoder, BitfieldValues)
{
    const uint32_t word = 5u | (31u << 3) | (13u << 8) | (1000u << 12);
    FieldDesc d         = FieldDesc::scalar(WireType::Bitfield, 4);
    d.bitfield          = bf(20, 4);
    std::string out;
    append_binary_value(out, d, reinterpret_cast<const unsigned char*>(&word), false);
    EXPECT_EQ(hex(out), "fdffffff");
    out.clear();
    // Phase 2 fix: swapped like any other 4-byte value.
    append_binary_value(out, d, reinterpret_cast<const unsigned char*>(&word), true);
    EXPECT_EQ(hex(out), "fffffffd");
    out.clear();
    append_ascii_value(out, d, reinterpret_cast<const unsigned char*>(&word), nullptr, "");
    EXPECT_EQ(out, "-3");
}

TEST(BinaryEncoder, ByteswapSwapsEachElement)
{
    const int32_t ints[] = { 10, 20 };
    std::string out;
    append_binary_value(out, FieldDesc::array(WireType::Integer, 4, 2), reinterpret_cast<const unsigned char*>(ints),
                        true);
    EXPECT_EQ(hex(out), "0000000a00000014");

    // Phase 0 fix: strings are bytes, so byteswap leaves them as they are.
    out.clear();
    append_binary_value(out, FieldDesc::narrow_string(2), reinterpret_cast<const unsigned char*>("hi"), true);
    EXPECT_EQ(out, std::string("hi\0", 3));

    // One indexed element: only its own bytes.
    out.clear();
    const double one = 1.0;
    append_binary_value(out, FieldDesc::scalar(WireType::Double, 8), reinterpret_cast<const unsigned char*>(&one),
                        true);
    EXPECT_EQ(hex(out), "3ff0000000000000");

    // Element sizes the old server could not swap are sent as zeros, as before.
    out.clear();
    const unsigned char sixteen[16] = { 1, 2, 3 };
    append_binary_value(out, FieldDesc::array(WireType::Structured, 16, 1), sixteen, true);
    EXPECT_EQ(out, std::string(16, '\0'));
}

TEST(BinaryEncoder, VariableLayout)
{
    const int32_t v = 7;
    std::string out;
    append_binary_var(out, "a.b", FieldDesc::scalar(WireType::Integer, 4), reinterpret_cast<const unsigned char*>(&v),
                      false, false);
    EXPECT_EQ(hex(out), "03000000" "612e62" "06000000" "04000000" "07000000");
    EXPECT_EQ(binary_var_size("a.b", FieldDesc::scalar(WireType::Integer, 4), false), out.size());
    out.clear();
    append_binary_var(out, "a.b", FieldDesc::scalar(WireType::Integer, 4), reinterpret_cast<const unsigned char*>(&v),
                      true, true);
    EXPECT_EQ(hex(out), "00000006" "00000004" "00000007");
    EXPECT_EQ(binary_var_size("a.b", FieldDesc::scalar(WireType::Integer, 4), true), out.size());
}

// ---------------------------------------------------------------------------
// Packetizer
// ---------------------------------------------------------------------------

namespace
{
    struct List
    {
            Snapshot snapshot;
            std::vector<std::string> names;
            std::vector<VarFormat> formats;

            template <class T> void add(const std::string& name, WireType type, const std::vector<T>& values)
            {
                snapshot.add(FieldDesc::array(type, sizeof(T), static_cast<uint32_t>(values.size())), values.data());
                names.push_back(name);
            }

            void add_text(const std::string& name, const std::string& text)
            {
                snapshot.add(FieldDesc::narrow_string(static_cast<uint32_t>(text.size())), text.c_str());
                names.push_back(name);
            }

            const std::vector<VarFormat>& fmt()
            {
                formats.clear();
                for (const std::string& n : names)
                {
                    VarFormat f;
                    f.name = n;
                    formats.push_back(f);
                }
                return formats;
            }
    };
} // namespace

TEST(Packetizer, AsciiMessage)
{
    List l;
    l.add<int>("a", WireType::Integer, { -1 });
    l.add<double>("b", WireType::Double, { 2.5 });
    Packets p;
    encode_ascii(p, l.snapshot, l.fmt(), MessageType::VarList);
    ASSERT_EQ(p.messages.size(), 1u);
    EXPECT_EQ(p.messages[0], "0\t-1\t2.5\n");
    p.clear();
    encode_ascii(p, l.snapshot, l.fmt(), MessageType::SendOnce);
    EXPECT_EQ(p.messages[0], "5\t-1\t2.5\n");
}

TEST(Packetizer, EmptyListSendsNothing)
{
    List l;
    Packets p;
    encode_ascii(p, l.snapshot, l.fmt(), MessageType::VarList);
    encode_binary(p, l.snapshot, l.fmt(), MessageType::VarList, false, false);
    EXPECT_TRUE(p.messages.empty());
}

TEST(Packetizer, SizesMustMatch)
{
    List l;
    l.add<int>("a", WireType::Integer, { 1 });
    Packets p;
    EXPECT_THROW(encode_ascii(p, l.snapshot, {}, MessageType::VarList), std::invalid_argument);
}

TEST(Packetizer, AsciiSplitsAsTheOldServer)
{
    // Two 5000-character values do not fit in one 8192-byte message.
    List l;
    l.add_text("a", std::string(5000, 'a'));
    l.add_text("b", std::string(5000, 'b'));
    l.add<int>("c", WireType::Integer, { 7 });
    Packets p;
    encode_ascii(p, l.snapshot, l.fmt(), MessageType::VarList);
    ASSERT_EQ(p.messages.size(), 2u);
    // The first message ends with the tab that belongs to the next value.
    EXPECT_EQ(p.messages[0], "0\t" + std::string(5000, 'a') + "\t");
    EXPECT_EQ(p.messages[1], std::string(5000, 'b') + "\t7\n");
}

TEST(Packetizer, AsciiTruncatesAHugeValue)
{
    List l;
    l.add_text("long", std::string(9000, 'x'));
    Packets p;
    encode_ascii(p, l.snapshot, l.fmt(), MessageType::VarList);
    ASSERT_EQ(p.messages.size(), 2u);
    EXPECT_EQ(p.messages[0], "0\t");
    EXPECT_EQ(p.messages[1], std::string(8190, 'x') + "\n");
    ASSERT_EQ(p.warnings.size(), 1u);
    EXPECT_NE(p.warnings[0].find("long, TRUNCATED IT"), std::string::npos);
}

TEST(Packetizer, BinaryHeader)
{
    List l;
    l.add<int>("i", WireType::Integer, { 7 });
    Packets p;
    encode_binary(p, l.snapshot, l.fmt(), MessageType::VarList, false, false);
    ASSERT_EQ(p.messages.size(), 1u);
    EXPECT_EQ(hex(p.messages[0]), "00000000" "19000000" "01000000" "01000000" "69" "06000000" "04000000" "07000000");
    p.clear();
    encode_binary(p, l.snapshot, l.fmt(), MessageType::SendOnce, true, true);
    EXPECT_EQ(hex(p.messages[0]), "00000005" "00000014" "00000001" "00000006" "00000004" "00000007");
}

TEST(Packetizer, BinarySkipsWhatCannotFitAndSplitsTheRest)
{
    List l;
    l.add<int>("a", WireType::Integer, { 1 });
    l.add<double>("big", WireType::Double, std::vector<double>(2000, 0.25)); // 16000 bytes
    l.add<double>("d", WireType::Double, std::vector<double>(600, 1.0));     // 4800 bytes
    l.add<double>("e", WireType::Double, std::vector<double>(600, 2.0));     // 4800 bytes
    Packets p;
    encode_binary(p, l.snapshot, l.fmt(), MessageType::VarList, false, false);
    ASSERT_EQ(p.warnings.size(), 1u);
    EXPECT_NE(p.warnings[0].find("big, SKIPPING IT"), std::string::npos);
    ASSERT_EQ(p.messages.size(), 2u);
    int32_t n0, n1;
    std::memcpy(&n0, p.messages[0].data() + 8, 4);
    std::memcpy(&n1, p.messages[1].data() + 8, 4);
    EXPECT_EQ(n0, 2); // a, d
    EXPECT_EQ(n1, 1); // e
    for (const std::string& m : p.messages)
    {
        EXPECT_LE(m.size(), max_message);
        int32_t size;
        std::memcpy(&size, m.data() + 4, 4);
        EXPECT_EQ(static_cast<std::size_t>(size), m.size() - 4);
    }
}

TEST(Packetizer, BinaryAllSkippedStillSendsAHeader)
{
    List l;
    l.add<double>("big", WireType::Double, std::vector<double>(2000, 0.25));
    Packets p;
    encode_binary(p, l.snapshot, l.fmt(), MessageType::VarList, false, false);
    ASSERT_EQ(p.messages.size(), 1u);
    EXPECT_EQ(hex(p.messages[0]), "00000000" "08000000" "00000000");
}

// ---------------------------------------------------------------------------
// Fixed replies
// ---------------------------------------------------------------------------

TEST(FixedReply, VarExists)
{
    EXPECT_EQ(var_exists_reply(true, false), "1\t1\n");
    EXPECT_EQ(var_exists_reply(false, false), "1\t0\n");
    EXPECT_EQ(hex(var_exists_reply(true, true)), "0100000001");
    EXPECT_EQ(hex(var_exists_reply(false, true)), "0100000000");
}

TEST(FixedReply, ListSize)
{
    EXPECT_EQ(list_size_reply(3, false), "3\t3\n");
    EXPECT_EQ(hex(list_size_reply(2, true)), "03000000" "00000000" "02000000");
}

TEST(FixedReply, StlSize)
{
    EXPECT_EQ(stl_size_reply(3, false), "6\t3\n");
    EXPECT_EQ(stl_size_reply(std::nullopt, false), "6\tBAD_REF\n");
    EXPECT_EQ(hex(stl_size_reply(3, true)), "06000000" "03000000");
    EXPECT_EQ(hex(stl_size_reply(std::nullopt, true)), "06000000" "00000000");
    EXPECT_EQ(stl_size_reply(int64_t(1) << 40, false), "6\t2147483647\n");
}

TEST(FixedReply, Files)
{
    EXPECT_EQ(file_header(62), "2\t62\n");
    // Phase 2 fix: 64-bit sizes; the old header wrapped at 4 GiB.
    EXPECT_EQ(file_header(uint64_t(5) << 30), "2\t5368709120\n");
    EXPECT_EQ(file_missing_reply(), "2\t-1\n");
}

TEST(FixedReply, Stdio)
{
    EXPECT_EQ(stdio_reply(1, "hello from stdio"), "4 1 16\nhello from stdio");
    EXPECT_EQ(stdio_reply(2, "error text\n"), "4 2 11\nerror text\n");
    EXPECT_EQ(stdio_reply(1, ""), "4 1 0\n");
}

// ---------------------------------------------------------------------------
// Units
// ---------------------------------------------------------------------------

TEST(Units, ChooseUnits)
{
    FakeResolver r;
    r.set_scalar("pos", WireType::Double, 1000.0, "m");
    r.set_scalar("n", WireType::Double, 1.0, "1");
    FakeUnitConverter u;
    u.add_name("ft", "ft");
    u.add_name("m", "m");
    u.add_name("1", "1");
    u.add_name("M", "m"); // an old Trick name
    u.add("m", "ft", 1 / 0.3048);

    auto pos = r.resolve("pos");

    auto ft = choose_units(*pos, "ft", u);
    ASSERT_TRUE(ft);
    ASSERT_TRUE(ft.value());
    EXPECT_EQ(ft.value()->units, "ft");
    ASSERT_TRUE(ft.value()->conversion);
    EXPECT_NEAR(ft.value()->conversion->apply(1000.0), 3280.84, 0.01);

    // "xx": the variable's own units, with no conversion.
    auto xx = choose_units(*pos, "xx", u);
    ASSERT_TRUE(xx);
    ASSERT_TRUE(xx.value());
    EXPECT_EQ(xx.value()->units, "m");
    EXPECT_FALSE(xx.value()->conversion);

    // An old Trick name prints as the name it maps to.
    auto m = choose_units(*pos, "M", u);
    ASSERT_TRUE(m);
    EXPECT_EQ(m.value()->units, "m");

    // "--" changes nothing, and is not an error.
    auto dashes = choose_units(*pos, "--", u);
    ASSERT_TRUE(dashes);
    EXPECT_FALSE(dashes.value());

    // Errors keep the current units.
    EXPECT_FALSE(choose_units(*pos, "not_a_unit", u));
    EXPECT_FALSE(choose_units(*pos, "1", u)); // not compatible
    auto bad = r.resolve("nope");
    EXPECT_FALSE(choose_units(*bad, "m", u));
    EXPECT_FALSE(choose_units(*bad, "--", u));
}
