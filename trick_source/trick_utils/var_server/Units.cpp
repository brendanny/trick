#include "trick/vs/Units.hh"

namespace Trick
{
    namespace vs
    {

        Expected<std::optional<UnitsChoice>> choose_units(const ResolvedVar& var, std::string_view requested,
                                                          UnitConverter& converter)
        {
            std::string wanted(requested);
            if (wanted == "xx")
                wanted = var.base_units();

            if (!var.resolved())
                return Error { "units error for [" + var.name() + "]: the name does not resolve" };

            if (wanted == "--")
                return std::optional<UnitsChoice> {};

            Expected<std::string> mapped = converter.canonical(wanted);
            if (!mapped)
                return Error { "units error for [" + var.name() + "] [" + wanted + "]: " + mapped.error().message };

            Expected<std::unique_ptr<Conversion>> conversion = converter.converter(var.base_units(), mapped.value());
            if (!conversion)
                return Error { "[" + var.name() + "] cannot convert units from [" + var.base_units() + "] to ["
                               + mapped.value() + "]: " + conversion.error().message };

            UnitsChoice choice;
            choice.conversion = std::shared_ptr<const Conversion>(std::move(conversion.value()));
            choice.units      = std::move(mapped.value());
            return std::optional<UnitsChoice>(std::move(choice));
        }

    } // namespace vs
} // namespace Trick
