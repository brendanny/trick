#include <gtest/gtest.h>
#include "trick/Unit.hh"

TEST(UnitsConsumer, ConvertsLengthAndTemperature) {
    Unit metres("m");
    EXPECT_DOUBLE_EQ(metres.Convert_to(2.0, "cm"), 200.0);
    Unit celsius("degC");
    EXPECT_NEAR(celsius.Convert_to(100.0, "degF"), 212.0, 1e-10);
}

TEST(UnitsConsumer, RejectsIncompatibleDimensions) {
    Unit metres("m");
    EXPECT_THROW(metres.Convert_to(1.0, "s"), Unit::CONVERSION_ERROR);
}
