/*
PURPOSE: (The session variable "time": simulation time in seconds.)

var_add("time") does not go to the Memory Manager. It stages the time of the
copy, as a double, and always prints " {s}" in ASCII (the session sets the
units to "s"). The time is the Snapshot's time_s, which the sampler sets
before it stages, so the value is the time of the copy on whichever thread
made it, and no other thread reads the executive's clock.
*/

#ifndef TRICK_VS_TIMEVAR_HH
#define TRICK_VS_TIMEVAR_HH

#include "trick/vs/Interfaces.hh"

#include <string>

namespace Trick
{
    namespace vs
    {

        class TimeVar : public ResolvedVar
        {
            public:
                static constexpr const char* variable_name = "time";

                TimeVar() = default;

                const std::string& name() const override;

                bool resolved() const override { return true; }

                const std::string& base_units() const override;

                /** Adds out.time_s as a double. */
                void stage(Snapshot& out, bool validate_address) override;

                uint64_t epoch() const override { return 0; }

                std::optional<int64_t> stl_size() const override { return std::nullopt; }
        };

    } // namespace vs
} // namespace Trick

#endif
