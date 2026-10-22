#include "trick/vs/WireTypes.hh"

#include <cstring>

#include <gtest/gtest.h>

using namespace Trick::vs;

// The numbers are part of the protocol: clients decode them.
TEST(WireTypes, TypeCodesMatchTheProtocol)
{
    EXPECT_EQ(static_cast<int32_t>(WireType::Character), 1);
    EXPECT_EQ(static_cast<int32_t>(WireType::String), 3);
    EXPECT_EQ(static_cast<int32_t>(WireType::Integer), 6);
    EXPECT_EQ(static_cast<int32_t>(WireType::Double), 11);
    EXPECT_EQ(static_cast<int32_t>(WireType::LongLong), 14);
    EXPECT_EQ(static_cast<int32_t>(WireType::Boolean), 17);
    EXPECT_EQ(static_cast<int32_t>(WireType::WideString), 19);
    EXPECT_EQ(static_cast<int32_t>(WireType::Enumerated), 21);
    EXPECT_EQ(static_cast<int32_t>(WireType::Stl), 24);
    EXPECT_EQ(static_cast<int32_t>(WireType::BadRef), 25);
}

TEST(WireTypes, MessageTypesMatchTheProtocol)
{
    EXPECT_EQ(static_cast<int32_t>(MessageType::IpError), -1);
    EXPECT_EQ(static_cast<int32_t>(MessageType::VarList), 0);
    EXPECT_EQ(static_cast<int32_t>(MessageType::VarExists), 1);
    EXPECT_EQ(static_cast<int32_t>(MessageType::SieResource), 2);
    EXPECT_EQ(static_cast<int32_t>(MessageType::ListSize), 3);
    EXPECT_EQ(static_cast<int32_t>(MessageType::Stdio), 4);
    EXPECT_EQ(static_cast<int32_t>(MessageType::SendOnce), 5);
    EXPECT_EQ(static_cast<int32_t>(MessageType::StlSize), 6);
}

TEST(WireTypes, ModesMatchVarSetArguments)
{
    EXPECT_EQ(static_cast<int32_t>(CopyMode::Async), 0);
    EXPECT_EQ(static_cast<int32_t>(CopyMode::Scheduled), 1);
    EXPECT_EQ(static_cast<int32_t>(CopyMode::TopOfFrame), 2);
    EXPECT_EQ(static_cast<int32_t>(WriteMode::Async), 0);
    EXPECT_EQ(static_cast<int32_t>(WriteMode::WhenCopied), 1);
}

TEST(WireTypes, EveryCodeHasAName)
{
    for (int32_t code = 0; code <= 25; ++code)
    {
        ASSERT_TRUE(is_wire_type(code)) << code;
        EXPECT_STRNE(wire_type_name(static_cast<WireType>(code)), "unknown") << code;
    }
    EXPECT_STREQ(wire_type_name(WireType::BadRef), "BAD_REF");
}

TEST(WireTypes, CodesOutsideTheRangeAreNotTypes)
{
    EXPECT_FALSE(is_wire_type(-1));
    EXPECT_FALSE(is_wire_type(26));
    EXPECT_STREQ(wire_type_name(static_cast<WireType>(99)), "unknown");
}
