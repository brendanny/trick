#include "trick/vs/Snapshot.hh"

#include <cstring>

#include <gtest/gtest.h>

using namespace Trick::vs;

TEST(Snapshot, StartsEmpty)
{
    Snapshot s;
    EXPECT_TRUE(s.empty());
    EXPECT_EQ(s.size(), 0u);
    EXPECT_TRUE(s.bytes().empty());
}

TEST(Snapshot, StoresValuesBackToBack)
{
    Snapshot s;
    const int32_t i   = -123456789;
    const double d    = 3.5;
    const char text[] = "hello";

    EXPECT_EQ(s.add(FieldDesc::scalar(WireType::Integer, 4), &i), 0u);
    EXPECT_EQ(s.add(FieldDesc::scalar(WireType::Double, 8), &d), 1u);
    EXPECT_EQ(s.add(FieldDesc::narrow_string(5), text), 2u);

    ASSERT_EQ(s.size(), 3u);
    EXPECT_EQ(s.value(0).offset, 0u);
    EXPECT_EQ(s.value(1).offset, 4u);
    EXPECT_EQ(s.value(2).offset, 12u);
    EXPECT_EQ(s.bytes().size(), 18u);

    int32_t i2;
    double d2;
    std::memcpy(&i2, s.data(0), sizeof i2);
    std::memcpy(&d2, s.data(1), sizeof d2);
    EXPECT_EQ(i2, i);
    EXPECT_EQ(d2, d);
    EXPECT_STREQ(reinterpret_cast<const char*>(s.data(2)), "hello");
}

TEST(Snapshot, CopiesTheBytes)
{
    Snapshot s;
    int32_t i = 7;
    s.add(FieldDesc::scalar(WireType::Integer, 4), &i);
    i = 8;
    int32_t staged;
    std::memcpy(&staged, s.data(0), sizeof staged);
    EXPECT_EQ(staged, 7);
}

TEST(Snapshot, BadRefIsZero)
{
    Snapshot s;
    s.add_bad_ref();
    ASSERT_EQ(s.size(), 1u);
    EXPECT_TRUE(s.value(0).desc.is_bad_ref());
    int32_t v = -1;
    std::memcpy(&v, s.data(0), sizeof v);
    EXPECT_EQ(v, 0);
}

TEST(Snapshot, EmptyValuesNeedNoData)
{
    Snapshot s;
    s.add(FieldDesc::array(WireType::Integer, 4, 0), nullptr);
    ASSERT_EQ(s.size(), 1u);
    EXPECT_EQ(s.value(0).desc.byte_size(), 0u);
    EXPECT_TRUE(s.bytes().empty());
}

TEST(Snapshot, ClearKeepsCapacity)
{
    Snapshot s;
    s.reserve(4, 64);
    const double d = 1.0;
    s.add(FieldDesc::scalar(WireType::Double, 8), &d);
    s.time_tics         = 5;
    const auto capacity = s.bytes().capacity();
    s.clear();
    EXPECT_TRUE(s.empty());
    EXPECT_EQ(s.time_tics, 0);
    EXPECT_EQ(s.bytes().capacity(), capacity);
}

TEST(Snapshot, OutOfRangeIndexThrows)
{
    Snapshot s;
    EXPECT_THROW(s.value(0), std::out_of_range);
    EXPECT_THROW(s.data(0), std::out_of_range);
}
