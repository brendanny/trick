#include "trick/vs/Schedule.hh"

#include <cmath>
#include <limits>

#include <gtest/gtest.h>

using namespace Trick::vs;

TEST(Schedule, DefaultsMatchTheOldServer)
{
    Schedule s = default_schedule(1000000);
    EXPECT_EQ(s.copy_mode, CopyMode::Async);
    EXPECT_EQ(s.write_mode, WriteMode::Async);
    EXPECT_DOUBLE_EQ(s.cycle_s, 0.1);
    EXPECT_EQ(s.cycle_tics, 100000);
    EXPECT_EQ(s.frame_multiple, 1u);
    EXPECT_EQ(s.frame_offset, 0u);
    EXPECT_EQ(s.freeze_frame_multiple, 1u);
    EXPECT_EQ(s.freeze_frame_offset, 0u);
    EXPECT_FALSE(s.paused);
}

TEST(Schedule, DefaultCycleIsAtLeastOneTic)
{
    // As the old server: 0.1 s at 1 tic/s truncates to 0, so it uses 1.
    EXPECT_EQ(default_schedule(1).cycle_tics, 1);
}

TEST(Schedule, CycleToTicsTruncates)
{
    auto t = cycle_to_tics(0.25, 1000000);
    ASSERT_TRUE(t);
    EXPECT_EQ(t.value(), 250000);
    auto u = cycle_to_tics(1.0000009, 1000000);
    ASSERT_TRUE(u);
    EXPECT_EQ(u.value(), 1000000);
}

// Phase 0 defect: var_cycle(0) then scheduled mode divided by zero.
TEST(Schedule, CycleMustBePositiveAndFinite)
{
    for (double bad : { 0.0, -1.0, std::nan(""), std::numeric_limits<double>::infinity() })
    {
        auto t = cycle_to_tics(bad, 1000000);
        EXPECT_FALSE(t) << bad;
        if (!t)
        {
            EXPECT_NE(t.error().message.find("var_cycle"), std::string::npos);
        }
    }
}

TEST(Schedule, CycleMustBeAtLeastOneTic)
{
    EXPECT_FALSE(cycle_to_tics(0.0000001, 1000000));
    EXPECT_TRUE(cycle_to_tics(0.000001, 1000000));
}

TEST(Schedule, CycleMustFitInTics) { EXPECT_FALSE(cycle_to_tics(1e300, 1000000)); }

TEST(Schedule, TicValueMustBePositive) { EXPECT_FALSE(cycle_to_tics(0.1, 0)); }

TEST(Schedule, CopyModes)
{
    EXPECT_EQ(copy_mode_from_int(0).value(), CopyMode::Async);
    EXPECT_EQ(copy_mode_from_int(1).value(), CopyMode::Scheduled);
    EXPECT_EQ(copy_mode_from_int(2).value(), CopyMode::TopOfFrame);
    EXPECT_FALSE(copy_mode_from_int(3));
    EXPECT_FALSE(copy_mode_from_int(-1));
}

TEST(Schedule, WriteModes)
{
    EXPECT_EQ(write_mode_from_int(0).value(), WriteMode::Async);
    EXPECT_EQ(write_mode_from_int(1).value(), WriteMode::WhenCopied);
    EXPECT_FALSE(write_mode_from_int(2));
}

TEST(Schedule, VarSyncModes)
{
    EXPECT_EQ(sync_modes(0), std::make_pair(CopyMode::Async, WriteMode::Async));
    EXPECT_EQ(sync_modes(1), std::make_pair(CopyMode::Scheduled, WriteMode::Async));
    EXPECT_EQ(sync_modes(2), std::make_pair(CopyMode::Scheduled, WriteMode::WhenCopied));
    // Any other value is 0, as in the old server.
    EXPECT_EQ(sync_modes(7), std::make_pair(CopyMode::Async, WriteMode::Async));
}

// The old server accepted a frame multiple of 0 and then took frame % 0.
TEST(Schedule, FrameMultipleMustBeAtLeastOne)
{
    EXPECT_FALSE(check_frame_multiple(0));
    EXPECT_FALSE(check_frame_multiple(-3));
    EXPECT_TRUE(check_frame_multiple(1));
    EXPECT_TRUE(check_frame_multiple(4294967295LL));
    EXPECT_FALSE(check_frame_multiple(4294967296LL));
}

TEST(Schedule, FirstScheduledTicsRoundsToTheCycle)
{
    EXPECT_EQ(first_scheduled_tics(0, 100), 100);
    EXPECT_EQ(first_scheduled_tics(250, 100), 300);
    EXPECT_EQ(first_scheduled_tics(300, 100), 400);
}

TEST(Schedule, TopOfFrameSelectsFrames)
{
    EXPECT_TRUE(top_of_frame_due(0, 1, 0));
    EXPECT_TRUE(top_of_frame_due(7, 1, 0));
    EXPECT_TRUE(top_of_frame_due(4, 4, 0));
    EXPECT_FALSE(top_of_frame_due(5, 4, 0));
    EXPECT_TRUE(top_of_frame_due(6, 4, 2));
    // An offset of at least the multiple never matches, as in the old server.
    EXPECT_FALSE(top_of_frame_due(4, 4, 4));
}

TEST(Schedule, Equality)
{
    Schedule a = default_schedule(1000000);
    Schedule b = a;
    EXPECT_EQ(a, b);
    b.paused = true;
    EXPECT_NE(a, b);
}
