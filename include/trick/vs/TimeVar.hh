/*
PURPOSE: (The session variable "time": simulation time in seconds.)

var_add("time") does not go to the Memory Manager. It stages the time of the
copy, as a double, and always prints " {s}" in ASCII (the session sets the
units to "s").
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

                /** `clock` must outlive the TimeVar. */
                explicit TimeVar(const Clock& clock)
                    : _clock(clock)
                {
                }

                const std::string& name() const override;

                bool resolved() const override { return true; }

                const std::string& base_units() const override;

                /** Adds time_tics / tic_value as a double. */
                void stage(Snapshot& out, bool validate_address) override;

                uint64_t epoch() const override { return 0; }

                std::optional<int64_t> stl_size() const override { return std::nullopt; }

            private:
                const Clock& _clock;
        };

    } // namespace vs
} // namespace Trick

#endif
