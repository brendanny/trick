/*
PURPOSE: (What the variable server needs from the rest of Trick.)

The core library and the session logic use only these interfaces. The
adapter in sim_services implements them with the Memory Manager, the
executive, UDUNITS and the Python input processor. Tests implement them
with the fakes in trick/vs/testing/Fakes.hh.
*/

#ifndef TRICK_VS_INTERFACES_HH
#define TRICK_VS_INTERFACES_HH

#include "trick/vs/Expected.hh"
#include "trick/vs/FieldDesc.hh"
#include "trick/vs/Snapshot.hh"

#include <cstdint>
#include <memory>
#include <string>
#include <string_view>

namespace Trick
{
    namespace vs
    {

        /**
         * A variable name that was looked up. It copies the current value into a
         * Snapshot when asked.
         */
        class ResolvedVar
        {
            public:
                virtual ~ResolvedVar();

                /** The name as the client sent it. */
                virtual const std::string& name() const = 0;

                /** False if the name did not resolve; stage() then adds BAD_REF. */
                virtual bool resolved() const = 0;

                /** The units the variable is declared with, for example "m". */
                virtual const std::string& base_units() const = 0;

                /**
                 * Copy the current value into `out`. Adds exactly one value. If
                 * `validate_address` is set, the pointers on the path are checked
                 * against the Memory Manager first; a bad pointer adds BAD_REF.
                 *
                 * Called with the Resolver's memory lock held for reading.
                 */
                virtual void stage(Snapshot& out, bool validate_address) = 0;

                /** The Resolver::memory_epoch() when this name was looked up. */
                virtual uint64_t epoch() const = 0;
        };

        class Resolver
        {
            public:
                virtual ~Resolver();

                /**
                 * Look up a name. Never returns null: a name that does not resolve
                 * gives a ResolvedVar with resolved() == false.
                 */
                virtual std::unique_ptr<ResolvedVar> resolve(std::string_view name) = 0;

                /**
                 * Increases each time simulation memory is replaced (checkpoint load).
                 * A ResolvedVar with an older epoch must be looked up again.
                 */
                virtual uint64_t memory_epoch() const = 0;
        };

        /** Simulation time and executive state. */
        class Clock
        {
            public:
                virtual ~Clock();

                virtual long long time_tics() const          = 0;
                virtual long long tic_value() const          = 0; ///< tics per second
                virtual long long frame_count() const        = 0;
                virtual long long freeze_time_tics() const   = 0;
                virtual long long freeze_frame_count() const = 0;
                virtual bool real_time() const               = 0;
                virtual int exec_mode() const                = 0; ///< SIM_MODE, as the beacon sends it
        };

        /** A units conversion from a variable's units to the units a client asked for. */
        class Conversion
        {
            public:
                virtual ~Conversion();

                virtual double apply(double value) const = 0;
        };

        class UnitConverter
        {
            public:
                virtual ~UnitConverter();

                /**
                 * A conversion from `from` to `to`. Fails if either name is not a unit
                 * or the units are not compatible. Old Trick unit names are mapped
                 * first. The caller handles "xx" (base units) and "--" (no conversion).
                 */
                virtual Expected<std::unique_ptr<Conversion>> converter(std::string_view from, std::string_view to) = 0;

                /** The canonical name of `units` (old Trick names mapped), or an error. */
                virtual Expected<std::string> canonical(std::string_view units) = 0;
        };

        /** Runs a line that is not a typed command, in the Python input processor. */
        class CommandFallback
        {
            public:
                virtual ~CommandFallback();

                /** Run `text`. An error holds Python's message. */
                virtual Expected<void> run(std::string_view text) = 0;
        };

    } // namespace vs
} // namespace Trick

#endif
