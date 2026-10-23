/*
PURPOSE: (A UnitConverter on UDUNITS, for the golden replay test only.)

It does what the old server did: map old Trick unit names
(map_trick_units_to_udunits), ut_parse both names, ut_get_converter. The
adapter in Phase 4 has its own, on Trick's UdUnits system. Built only when
VS_HAVE_UDUNITS is defined.
*/

#ifndef VS_TEST_UDUNITSCONVERTER_HH
#define VS_TEST_UDUNITSCONVERTER_HH

#ifdef VS_HAVE_UDUNITS

#include "trick/vs/Interfaces.hh"

#include <map>
#include <memory>
#include <string>
#include <vector>

extern "C"
{
#include <udunits2.h>
}

namespace vs_test
{
    using namespace Trick::vs;

    /** A copy of Trick's map_trick_units_to_udunits(), so this test needs no Trick library. */
    inline std::string map_old_trick_units(const std::string& units)
    {
        static const std::map<std::string, std::string> old_to_ud = {
            { "r", "rad" },         { "d", "degree" },  { "as", "arcsecond" }, { "am", "arcminute" },
            { "rev", "revolution" }, { "M", "m" },       { "n.m.", "nmile" },   { "sl", "slug" },
            { "mt", "t" },           { "lbm", "lb" },    { "oz", "ozf" },       { "v", "V" },
            { "F", "degF" },         { "C", "degC" },    { "R", "degR" },       { "TNT", "ton_TNT" },
            { "Wh", "(W*h)" },       { "kWh", "(kW*h)" }, { "gal", "gallon" },  { "dB", "1" },
            { "one", "1" },          { "cnt", "count" }, { "--", "1" },
        };
        const std::string delimiters = "*/^()";
        std::vector<std::string> tokens;
        std::string::size_type last = units.find_first_not_of(delimiters, 0);
        if (last != 0)
            tokens.push_back(units.substr(0, last));
        std::string::size_type pos = units.find_first_of(delimiters, last);
        while (pos != std::string::npos || last != std::string::npos)
        {
            tokens.push_back(units.substr(last, pos - last));
            last = units.find_first_not_of(delimiters, pos);
            if (last != std::string::npos)
                tokens.push_back(units.substr(pos, last - pos));
            else if (pos != std::string::npos)
                tokens.push_back(units.substr(pos));
            pos = units.find_first_of(delimiters, last);
        }
        std::string out;
        for (std::string t : tokens)
        {
            const char last_char = t.empty() ? '\0' : t.back();
            const bool power     = last_char == '2' || last_char == '3';
            if (power)
                t.pop_back();
            auto it = old_to_ud.find(t);
            if (it != old_to_ud.end())
                t = it->second;
            if (power)
                t += last_char;
            out += t;
        }
        return out;
    }

    class UdunitsConversion : public Conversion
    {
        public:
            explicit UdunitsConversion(cv_converter* c)
                : _c(c)
            {
            }

            ~UdunitsConversion() override { cv_free(_c); }

            double apply(double value) const override { return cv_convert_double(_c, value); }

        private:
            cv_converter* _c;
    };

    class UdunitsConverter : public UnitConverter
    {
        public:
            UdunitsConverter()
            {
                ut_set_error_message_handler(ut_ignore);
                _system = ut_read_xml(nullptr);
            }

            ~UdunitsConverter() override
            {
                if (_system != nullptr)
                    ut_free_system(_system);
            }

            bool ok() const { return _system != nullptr; }

            Expected<std::string> canonical(std::string_view units) override
            {
                const std::string mapped = map_old_trick_units(std::string(units));
                ut_unit* u               = ut_parse(_system, mapped.c_str(), UT_ASCII);
                if (u == nullptr)
                    return Error { "not a unit: [" + mapped + "]" };
                ut_free(u);
                return mapped;
            }

            Expected<std::unique_ptr<Conversion>> converter(std::string_view from, std::string_view to) override
            {
                ut_unit* f = ut_parse(_system, std::string(from).c_str(), UT_ASCII);
                ut_unit* t = ut_parse(_system, map_old_trick_units(std::string(to)).c_str(), UT_ASCII);
                cv_converter* c = (f != nullptr && t != nullptr) ? ut_get_converter(f, t) : nullptr;
                ut_free(f);
                ut_free(t);
                if (c == nullptr)
                    return Error { "cannot convert units" };
                if (c == cv_get_trivial())
                    return std::unique_ptr<Conversion>();
                return std::unique_ptr<Conversion>(new UdunitsConversion(c));
            }

        private:
            ut_system* _system = nullptr;
    };

} // namespace vs_test

#endif // VS_HAVE_UDUNITS

#endif
