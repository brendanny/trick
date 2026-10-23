/*
PURPOSE: (Choose the units a variable is sent in: var_add(name, units) and var_units.)

The rules are the old server's (VariableReference::setRequestedUnits):

  * "xx" means the variable's own units.
  * A name that did not resolve keeps no units (an error).
  * "--" changes nothing.
  * Otherwise the old Trick name is mapped (for example "d" to "degree"), and
    a conversion from the variable's units is made. If that fails, nothing
    changes. If it works, the value is sent converted, followed by the mapped
    name in braces.
*/

#ifndef TRICK_VS_UNITS_HH
#define TRICK_VS_UNITS_HH

#include "trick/vs/Expected.hh"
#include "trick/vs/Interfaces.hh"

#include <memory>
#include <optional>
#include <string>
#include <string_view>

namespace Trick
{
    namespace vs
    {

        struct UnitsChoice
        {
                /** Null when the conversion is the identity. */
                std::shared_ptr<const Conversion> conversion;
                /** The name to print in braces. */
                std::string units;
        };

        /**
         * The new units for `var`. An Error means "keep the current units"; so
         * does an empty optional (for "--"), which is not an error.
         */
        Expected<std::optional<UnitsChoice>> choose_units(const ResolvedVar& var, std::string_view requested,
                                                          UnitConverter& converter);

    } // namespace vs
} // namespace Trick

#endif
