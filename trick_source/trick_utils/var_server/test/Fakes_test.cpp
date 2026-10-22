#include "trick/vs/testing/Fakes.hh"

#include <cstring>

#include <gtest/gtest.h>

using namespace Trick::vs;
using namespace Trick::vs::testing;

TEST(FakeResolver, ResolvesKnownNames)
{
    FakeResolver r;
    r.set_scalar("conf.i32", WireType::Integer, int32_t { -5 }, "m");
    auto var = r.resolve("conf.i32");
    ASSERT_TRUE(var->resolved());
    EXPECT_EQ(var->name(), "conf.i32");
    EXPECT_EQ(var->base_units(), "m");
    EXPECT_EQ(var->epoch(), 1u);

    Snapshot s;
    var->stage(s, false);
    ASSERT_EQ(s.size(), 1u);
    int32_t v;
    std::memcpy(&v, s.data(0), sizeof v);
    EXPECT_EQ(v, -5);
}

TEST(FakeResolver, UnknownNamesStageBadRef)
{
    FakeResolver r;
    auto var = r.resolve("nope");
    EXPECT_FALSE(var->resolved());
    Snapshot s;
    var->stage(s, false);
    ASSERT_EQ(s.size(), 1u);
    EXPECT_TRUE(s.value(0).desc.is_bad_ref());
}

TEST(FakeResolver, ValueChangesAreSeenAtTheNextStage)
{
    FakeResolver r;
    auto backing     = r.set_scalar("x", WireType::Double, 1.0);
    auto var         = r.resolve("x");
    const double two = 2.0;
    std::memcpy(backing->bytes.data(), &two, sizeof two);
    Snapshot s;
    var->stage(s, false);
    double v;
    std::memcpy(&v, s.data(0), sizeof v);
    EXPECT_EQ(v, 2.0);
}

TEST(FakeResolver, BadAddressIsBadRefOnlyWhenValidating)
{
    FakeResolver r;
    auto backing           = r.set_scalar("p", WireType::Integer, int32_t { 1 });
    backing->valid_address = false;
    auto var               = r.resolve("p");
    Snapshot s;
    var->stage(s, false);
    var->stage(s, true);
    EXPECT_FALSE(s.value(0).desc.is_bad_ref());
    EXPECT_TRUE(s.value(1).desc.is_bad_ref());
}

TEST(FakeResolver, EpochIsRecordedAtResolve)
{
    FakeResolver r;
    r.set_scalar("x", WireType::Integer, int32_t { 0 });
    auto before = r.resolve("x");
    r.epoch     = 2;
    EXPECT_EQ(before->epoch(), 1u);
    EXPECT_EQ(r.memory_epoch(), 2u);
}

TEST(FakeUnitConverter, ConvertsOnlyWhatWasAdded)
{
    FakeUnitConverter u;
    u.add("m", "ft", 3.28083989501312);
    u.add("degC", "degF", 1.8, 32.0);
    auto ft = u.converter("m", "ft");
    ASSERT_TRUE(ft);
    EXPECT_NEAR(ft.value()->apply(1000.0), 3280.84, 1e-2);
    auto f = u.converter("degC", "degF");
    ASSERT_TRUE(f);
    EXPECT_DOUBLE_EQ(f.value()->apply(100.0), 212.0);
    EXPECT_FALSE(u.converter("m", "s"));
}

TEST(FakeCommandFallback, RecordsLinesAndCanFail)
{
    FakeCommandFallback f;
    EXPECT_TRUE(f.run("x = 1"));
    f.fail_with = "SyntaxError";
    auto r      = f.run("not python");
    EXPECT_FALSE(r);
    EXPECT_EQ(r.error().message, "SyntaxError");
    ASSERT_EQ(f.lines.size(), 2u);
    EXPECT_EQ(f.lines[1], "not python");
}

TEST(FakeClock, ReturnsItsFields)
{
    FakeClock c;
    c.time         = 123;
    c.frame        = 4;
    c.is_real_time = true;
    EXPECT_EQ(c.time_tics(), 123);
    EXPECT_EQ(c.frame_count(), 4);
    EXPECT_TRUE(c.real_time());
    EXPECT_EQ(c.tic_value(), 1000000);
}
