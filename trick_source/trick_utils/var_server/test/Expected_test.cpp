#include "trick/vs/Expected.hh"

#include <memory>
#include <variant>

#include <gtest/gtest.h>

using namespace Trick::vs;

TEST(Expected, HoldsAValue)
{
    Expected<int> e = 42;
    ASSERT_TRUE(e);
    EXPECT_TRUE(e.has_value());
    EXPECT_EQ(e.value(), 42);
}

TEST(Expected, HoldsAnError)
{
    Expected<int> e = Error { "bad" };
    ASSERT_FALSE(e);
    EXPECT_EQ(e.error().message, "bad");
    EXPECT_THROW(e.value(), std::bad_variant_access);
}

TEST(Expected, MovesOutMoveOnlyValues)
{
    Expected<std::unique_ptr<int>> e = std::make_unique<int>(5);
    ASSERT_TRUE(e);
    std::unique_ptr<int> p = std::move(e).value();
    ASSERT_NE(p, nullptr);
    EXPECT_EQ(*p, 5);
}

TEST(Expected, VoidIsSuccessOrError)
{
    Expected<void> ok;
    EXPECT_TRUE(ok);
    Expected<void> bad = Error { "no" };
    EXPECT_FALSE(bad);
    EXPECT_EQ(bad.error().message, "no");
}

TEST(Expected, StringValueIsNotTakenForAnError)
{
    Expected<std::string> e = std::string("m");
    ASSERT_TRUE(e);
    EXPECT_EQ(e.value(), "m");
}
