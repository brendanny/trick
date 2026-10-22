#include "trick/vs/Schedule.hh"

#include <cmath>
#include <cstdio>
#include <limits>

namespace Trick
{
    namespace vs
    {

        bool operator==(const Schedule& a, const Schedule& b) noexcept
        {
            return a.copy_mode == b.copy_mode && a.write_mode == b.write_mode && a.cycle_s == b.cycle_s
                && a.cycle_tics == b.cycle_tics && a.frame_multiple == b.frame_multiple
                && a.frame_offset == b.frame_offset && a.freeze_frame_multiple == b.freeze_frame_multiple
                && a.freeze_frame_offset == b.freeze_frame_offset && a.paused == b.paused;
        }

        bool operator!=(const Schedule& a, const Schedule& b) noexcept { return !(a == b); }

        Schedule default_schedule(long long tic_value) noexcept
        {
            Schedule s;
            // As the old server: truncate, and use 1 tic if the period is shorter.
            long long tics = static_cast<long long>(default_cycle_s * static_cast<double>(tic_value));
            s.cycle_tics   = tics > 0 ? tics : 1;
            return s;
        }

        Expected<long long> cycle_to_tics(double seconds, long long tic_value)
        {
            char msg[160];
            if (tic_value <= 0)
            {
                std::snprintf(msg, sizeof msg, "the time tic value %lld is not positive", tic_value);
                return Error { msg };
            }
            if (!std::isfinite(seconds) || seconds <= 0.0)
            {
                std::snprintf(msg, sizeof msg, "var_cycle(%g): the period must be greater than 0", seconds);
                return Error { msg };
            }
            const double tics = seconds * static_cast<double>(tic_value);
            // 2^63 is the first double that does not fit in a long long.
            if (tics >= 9223372036854775808.0)
            {
                std::snprintf(msg, sizeof msg, "var_cycle(%g): the period is too long", seconds);
                return Error { msg };
            }
            const long long whole = static_cast<long long>(tics);
            if (whole < 1)
            {
                std::snprintf(msg, sizeof msg, "var_cycle(%g): the period is shorter than one time tic (1/%lld s)",
                              seconds, tic_value);
                return Error { msg };
            }
            return whole;
        }

        Expected<CopyMode> copy_mode_from_int(int mode)
        {
            switch (mode)
            {
            case 0:
                return CopyMode::Async;
            case 1:
                return CopyMode::Scheduled;
            case 2:
                return CopyMode::TopOfFrame;
            default:
                break;
            }
            char msg[80];
            std::snprintf(msg, sizeof msg, "var_set_copy_mode(%d): the mode must be 0, 1 or 2", mode);
            return Error { msg };
        }

        Expected<WriteMode> write_mode_from_int(int mode)
        {
            switch (mode)
            {
            case 0:
                return WriteMode::Async;
            case 1:
                return WriteMode::WhenCopied;
            default:
                break;
            }
            char msg[80];
            std::snprintf(msg, sizeof msg, "var_set_write_mode(%d): the mode must be 0 or 1", mode);
            return Error { msg };
        }

        std::pair<CopyMode, WriteMode> sync_modes(int mode) noexcept
        {
            switch (mode)
            {
            case 1:
                return { CopyMode::Scheduled, WriteMode::Async };
            case 2:
                return { CopyMode::Scheduled, WriteMode::WhenCopied };
            default:
                return { CopyMode::Async, WriteMode::Async };
            }
        }

        Expected<void> check_frame_multiple(long long multiple)
        {
            if (multiple < 1 || multiple > std::numeric_limits<uint32_t>::max())
            {
                char msg[96];
                std::snprintf(msg, sizeof msg, "frame multiple %lld: it must be from 1 to 4294967295", multiple);
                return Error { msg };
            }
            return { };
        }

        long long first_scheduled_tics(long long now_tics, long long cycle_tics) noexcept
        {
            return now_tics - now_tics % cycle_tics + cycle_tics;
        }

        bool top_of_frame_due(long long frame, uint32_t multiple, uint32_t offset) noexcept
        {
            return frame % static_cast<long long>(multiple) == static_cast<long long>(offset);
        }

    } // namespace vs
} // namespace Trick
