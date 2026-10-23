// Adapter: units conversions on Trick's UDUNITS system (rewrite Phase 4).
// See include/trick/vs/adapter/UdUnitsConverter.hh.

#include "trick/vs/adapter/UdUnitsConverter.hh"

#include "trick/UdUnits.hh"
#include "trick/map_trick_units_to_udunits.hh"

namespace Trick
{
    namespace vs
    {
        namespace adapter
        {

            namespace
            {
                class UdUnitsConversion : public Conversion
                {
                    public:
                        explicit UdUnitsConversion(cv_converter* c) noexcept
                            : _c(c)
                        {
                        }

                        ~UdUnitsConversion() override { cv_free(_c); }

                        double apply(double value) const override { return cv_convert_double(_c, value); }

                    private:
                        cv_converter* _c;
                };

                struct UnitFree
                {
                        void operator()(ut_unit* u) const noexcept { ut_free(u); }
                };

                using UnitPtr = std::unique_ptr<ut_unit, UnitFree>;
            } // namespace

            std::mutex& UdUnitsConverter::lock() noexcept
            {
                static std::mutex m;
                return m;
            }

            ut_system* UdUnitsConverter::system() const noexcept
            {
                return _system != nullptr ? _system : Trick::UdUnits::get_u_system();
            }

            Expected<std::string> UdUnitsConverter::canonical(std::string_view units)
            {
                const std::string mapped = map_trick_units_to_udunits(std::string(units));
                std::lock_guard<std::mutex> guard(lock());
                ut_system* sys = system();
                if (sys == nullptr)
                    return Error { "the UDUNITS unit system is not loaded" };
                UnitPtr u(ut_parse(sys, mapped.c_str(), UT_ASCII));
                if (!u)
                    return Error { "not a unit: [" + mapped + "]" };
                return mapped;
            }

            Expected<std::unique_ptr<Conversion>> UdUnitsConverter::converter(std::string_view from, std::string_view to)
            {
                const std::string from_text(from);
                const std::string to_text = map_trick_units_to_udunits(std::string(to));
                std::lock_guard<std::mutex> guard(lock());
                ut_system* sys = system();
                if (sys == nullptr)
                    return Error { "the UDUNITS unit system is not loaded" };
                // The variable's own units are parsed as they are, as the old server did.
                UnitPtr f(ut_parse(sys, from_text.c_str(), UT_ASCII));
                if (!f)
                    return Error { "cannot interpret the variable's units [" + from_text + "]" };
                UnitPtr t(ut_parse(sys, to_text.c_str(), UT_ASCII));
                if (!t)
                    return Error { "cannot interpret the requested units [" + to_text + "]" };
                cv_converter* c = ut_get_converter(f.get(), t.get());
                if (c == nullptr)
                    return Error { "cannot convert units from [" + from_text + "] to [" + to_text + "]" };
                if (c == cv_get_trivial())
                    return std::unique_ptr<Conversion>();
                return std::unique_ptr<Conversion>(new UdUnitsConversion(c));
            }

        } // namespace adapter
    } // namespace vs
} // namespace Trick
