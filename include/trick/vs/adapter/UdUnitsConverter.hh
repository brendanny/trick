/*
PURPOSE: (Units conversions for the variable server, on Trick's UDUNITS system.)

As the old server did (VariableReference::setRequestedUnits): an old Trick
unit name is mapped (map_trick_units_to_udunits), both names are parsed,
and ut_get_converter() makes the conversion.

UDUNITS is not thread-safe, so one lock guards every call on the shared
ut_system. A finished converter is read-only, so Conversion::apply() takes
no lock. The old server used the system from session threads with no lock.
*/

#ifndef TRICK_VS_ADAPTER_UDUNITSCONVERTER_HH
#define TRICK_VS_ADAPTER_UDUNITSCONVERTER_HH

#include "trick/vs/Interfaces.hh"

#include <memory>
#include <mutex>
#include <string>
#include <string_view>

#include <udunits2.h>

namespace Trick
{
    namespace vs
    {
        namespace adapter
        {

            class UdUnitsConverter : public UnitConverter
            {
                public:
                    /** On `system`; null uses Trick::UdUnits::get_u_system() at each call. */
                    explicit UdUnitsConverter(ut_system* system = nullptr) noexcept
                        : _system(system)
                    {
                    }

                    Expected<std::unique_ptr<Conversion>> converter(std::string_view from, std::string_view to) override;

                    Expected<std::string> canonical(std::string_view units) override;

                    /** The lock every UDUNITS call in the variable server takes. */
                    static std::mutex& lock() noexcept;

                private:
                    ut_system* system() const noexcept;

                    ut_system* _system;
            };

        } // namespace adapter
    } // namespace vs
} // namespace Trick

#endif
