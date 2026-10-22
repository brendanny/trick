/*
PURPOSE: (When a session copies and sends: modes, cycle, frame selection.)

A session thread builds a new Schedule for each change and publishes it; the
main thread reads the published copy. The functions here are pure, so the
timing rules can be tested without a simulation.
*/

#ifndef TRICK_VS_SCHEDULE_HH
#define TRICK_VS_SCHEDULE_HH

#include "trick/vs/Expected.hh"
#include "trick/vs/WireTypes.hh"

#include <cstdint>
#include <limits>
#include <utility>

namespace Trick
{
    namespace vs
    {

        /** next_tics value that means "never". The same as TRICK_MAX_LONG_LONG. */
        constexpr long long never_tics = std::numeric_limits<long long>::max();

        /** The default var_cycle period. */
        constexpr double default_cycle_s = 0.1;

        struct Schedule
        {
                CopyMode copy_mode             = CopyMode::Async;
                WriteMode write_mode           = WriteMode::Async;
                double cycle_s                 = default_cycle_s;
                long long cycle_tics           = 0; ///< set from cycle_s by cycle_to_tics()
                uint32_t frame_multiple        = 1;
                uint32_t frame_offset          = 0;
                uint32_t freeze_frame_multiple = 1;
                uint32_t freeze_frame_offset   = 0;
                bool paused                    = false;
        };

        bool operator==(const Schedule& a, const Schedule& b) noexcept;
        bool operator!=(const Schedule& a, const Schedule& b) noexcept;

        /** The default schedule for a sim with `tic_value` tics per second. */
        Schedule default_schedule(long long tic_value) noexcept;

        /**
         * Convert a var_cycle period to tics. The period must be finite and greater
         * than 0, and must be at least one tic. (The old server accepted 0 and then
         * divided by zero.)
         */
        Expected<long long> cycle_to_tics(double seconds, long long tic_value);

        /** Copy mode from a var_set_copy_mode argument: 0, 1 or 2. */
        Expected<CopyMode> copy_mode_from_int(int mode);

        /** Write mode from a var_set_write_mode argument: 0 or 1. */
        Expected<WriteMode> write_mode_from_int(int mode);

        /**
         * The modes for var_sync(mode): 1 is scheduled/async, 2 is
         * scheduled/when-copied, anything else is async/async (as the old server).
         */
        std::pair<CopyMode, WriteMode> sync_modes(int mode) noexcept;

        /** A frame multiple must be at least 1. (The old server accepted 0.) */
        Expected<void> check_frame_multiple(long long multiple);

        /**
         * The first scheduled copy time after a session enters scheduled mode:
         * `now` rounded down to a multiple of the cycle, plus one cycle.
         * Precondition: cycle_tics > 0 and now >= 0.
         */
        long long first_scheduled_tics(long long now_tics, long long cycle_tics) noexcept;

        /** True if a top-of-frame session copies on this frame. Precondition: multiple >= 1. */
        bool top_of_frame_due(long long frame, uint32_t multiple, uint32_t offset) noexcept;

    } // namespace vs
} // namespace Trick

#endif
