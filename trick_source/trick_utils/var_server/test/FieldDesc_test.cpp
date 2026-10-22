#include "trick/vs/FieldDesc.hh"

#include <gtest/gtest.h>

using namespace Trick::vs;

TEST(FieldDesc, BadRefIsOneZeroInt)
{
    FieldDesc d = FieldDesc::bad_ref();
    EXPECT_EQ(d.type, WireType::BadRef);
    EXPECT_EQ(d.element_size, 4u);
    EXPECT_EQ(d.count, 1u);
    EXPECT_EQ(d.byte_size(), 4u);
    EXPECT_TRUE(d.is_bad_ref());
    EXPECT_EQ(validate(d), nullptr);
}

TEST(FieldDesc, DefaultIsInvalid)
{
    // A default FieldDesc is BAD_REF with no bytes, which the encoders refuse.
    EXPECT_NE(validate(FieldDesc { }), nullptr);
}

TEST(FieldDesc, ByteSizeIsElementSizeTimesCount)
{
    EXPECT_EQ(FieldDesc::array(WireType::Double, 8, 6).byte_size(), 48u);
    EXPECT_EQ(FieldDesc::array(WireType::Integer, 4, 0).byte_size(), 0u);
}

TEST(FieldDesc, NarrowStringCountsTheNul)
{
    FieldDesc d = FieldDesc::narrow_string(16);
    EXPECT_EQ(d.type, WireType::String);
    EXPECT_EQ(d.count, 17u);
    EXPECT_EQ(d.text, Text::Narrow);
    EXPECT_EQ(validate(d), nullptr);
}

TEST(FieldDesc, WideStringUsesWcharSize)
{
    FieldDesc d = FieldDesc::wide_string(5);
    EXPECT_EQ(d.type, WireType::WideString);
    EXPECT_EQ(d.element_size, sizeof(wchar_t));
    EXPECT_EQ(d.count, 6u);
    EXPECT_EQ(d.text, Text::Wide);
    EXPECT_EQ(validate(d), nullptr);
}

TEST(FieldDesc, CharArrayIsTypeOneWithTextInAscii)
{
    FieldDesc d = FieldDesc::char_array(8);
    EXPECT_EQ(d.type, WireType::Character);
    EXPECT_EQ(d.byte_size(), 8u);
    EXPECT_EQ(d.text, Text::Narrow);
    EXPECT_EQ(validate(d), nullptr);
}

// Phase 0 fix: an enum's element size is its real size.
TEST(FieldDesc, EnumsMayHaveAnyIntegerSize)
{
    for (uint32_t size : { 1u, 2u, 4u, 8u })
    {
        EXPECT_EQ(validate(FieldDesc::scalar(WireType::Enumerated, size)), nullptr) << size;
    }
    EXPECT_NE(validate(FieldDesc::scalar(WireType::Enumerated, 3)), nullptr);
}

TEST(FieldDesc, FixedSizeTypesRejectOtherSizes)
{
    EXPECT_EQ(validate(FieldDesc::scalar(WireType::Double, 8)), nullptr);
    EXPECT_NE(validate(FieldDesc::scalar(WireType::Double, 4)), nullptr);
    EXPECT_NE(validate(FieldDesc::scalar(WireType::Short, 4)), nullptr);
    EXPECT_NE(validate(FieldDesc::scalar(WireType::Boolean, 4)), nullptr);
    EXPECT_EQ(validate(FieldDesc::scalar(WireType::Long, 4)), nullptr);
    EXPECT_EQ(validate(FieldDesc::scalar(WireType::Long, 8)), nullptr);
}

TEST(FieldDesc, BitfieldMustFitItsStorage)
{
    FieldDesc d = FieldDesc::scalar(WireType::Bitfield, 4);
    d.bitfield  = { 28, 4 };
    EXPECT_EQ(validate(d), nullptr);
    d.bitfield = { 30, 4 };
    EXPECT_NE(validate(d), nullptr);
    d.bitfield = { 0, 0 };
    EXPECT_NE(validate(d), nullptr);
}

TEST(FieldDesc, OnlyBitfieldsHaveABitPosition)
{
    FieldDesc d = FieldDesc::scalar(WireType::Integer, 4);
    d.bitfield  = { 0, 3 };
    EXPECT_NE(validate(d), nullptr);
}

TEST(FieldDesc, NarrowTextNeedsOneByteElements)
{
    FieldDesc d = FieldDesc::array(WireType::Integer, 4, 2);
    d.text      = Text::Narrow;
    EXPECT_NE(validate(d), nullptr);
}

TEST(FieldDesc, PointersAndOpaqueValuesHaveAnySize)
{
    EXPECT_EQ(validate(FieldDesc::scalar(WireType::VoidPtr, 8)), nullptr);
    EXPECT_EQ(validate(FieldDesc::scalar(WireType::Structured, 24)), nullptr);
    EXPECT_EQ(validate(FieldDesc::scalar(WireType::Stl, 24)), nullptr);
}

TEST(FieldDesc, RejectsValuesOver4GiB)
{
    EXPECT_NE(validate(FieldDesc::array(WireType::Double, 8, 1u << 30)), nullptr);
}

TEST(FieldDesc, Equality)
{
    EXPECT_EQ(FieldDesc::char_array(8), FieldDesc::char_array(8));
    EXPECT_NE(FieldDesc::char_array(8), FieldDesc::char_array(9));
    FieldDesc a      = FieldDesc::scalar(WireType::Double, 8);
    FieldDesc b      = a;
    b.units_dashdash = true;
    EXPECT_NE(a, b);
}
