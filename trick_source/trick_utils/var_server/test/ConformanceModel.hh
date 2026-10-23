/*
PURPOSE: (The variables of test/SIM_vs_conformance, as a FakeResolver.)

Each entry is what the adapter (Phase 4) will stage for that name in the
conformance SIM: the values come from ConfVars.cpp, the descriptions from
the old server's choices that the golden captures recorded. A name that is
not here does not resolve (BAD_REF), as for vptr, fp, inner, bits and
inner_ptr, which the old server sent as BAD_REF.
*/

#ifndef VS_TEST_CONFORMANCEMODEL_HH
#define VS_TEST_CONFORMANCEMODEL_HH

#include "trick/vs/testing/Fakes.hh"

#include <climits>
#include <cmath>
#include <cstring>
#include <limits>
#include <string>
#include <vector>

namespace vs_test
{
    using namespace Trick::vs;
    using namespace Trick::vs::testing;

    inline void add_text(FakeResolver& r, const std::string& name, const std::string& text)
    {
        r.set(name, FieldDesc::narrow_string(static_cast<uint32_t>(text.size())), text.c_str());
    }

    inline void add_wide(FakeResolver& r, const std::string& name, const std::wstring& text)
    {
        r.set(name, FieldDesc::wide_string(static_cast<uint32_t>(text.size())), text.c_str());
    }

    template <class T>
    void add_array(FakeResolver& r, const std::string& name, WireType type, const std::vector<T>& values,
                   const std::string& units = "1")
    {
        r.set(name, FieldDesc::array(type, sizeof(T), static_cast<uint32_t>(values.size())), values.data(), units);
    }

    inline void add_bitfield(FakeResolver& r, const std::string& name, WireType type, uint32_t word, uint16_t start,
                             uint16_t width)
    {
        FieldDesc d      = FieldDesc::scalar(type, 4);
        d.bitfield.start = start;
        d.bitfield.width = width;
        r.set(name, d, &word, "1");
    }

    /**
     * The Memory Manager's name parser skips white space around a name, so
     * var_send_once("a, b") finds " b". This resolver does the same with the
     * model; the ResolvedVar keeps the name as the client sent it.
     */
    class ConformanceResolver : public Resolver
    {
        public:
            explicit ConformanceResolver(FakeResolver& model)
                : _model(model)
            {
            }

            std::unique_ptr<ResolvedVar> resolve(std::string_view name) override
            {
                const std::size_t first = name.find_first_not_of(" \t");
                const std::size_t last  = name.find_last_not_of(" \t");
                const std::string trimmed =
                    first == std::string_view::npos ? std::string() : std::string(name.substr(first, last - first + 1));
                return std::make_unique<FakeResolvedVar>(std::string(name), _model.find(trimmed), _model.epoch);
            }

            uint64_t memory_epoch() const override { return _model.epoch; }

        private:
            FakeResolver& _model;
    };

    /** Fill `r` with the conformance SIM's variables. */
    inline void build_conformance_model(FakeResolver& r)
    {
        const std::string P = "conf.vars.";
        const double pi     = 3.141592653589793;

        // Scalars
        r.set_scalar(P + "c", WireType::Character, 'A', "1");
        r.set_scalar(P + "sc", WireType::Character, static_cast<signed char>(-5), "1");
        r.set_scalar(P + "uc", WireType::UnsignedCharacter, static_cast<unsigned char>(200), "1");
        r.set_scalar(P + "s", WireType::Short, static_cast<short>(-1234), "1");
        r.set_scalar(P + "us", WireType::UnsignedShort, static_cast<unsigned short>(54321), "1");
        r.set_scalar(P + "i32", WireType::Integer, -123456789, "1");
        r.set_scalar(P + "u32", WireType::UnsignedInteger, 4000000000u, "1");
        r.set_scalar(P + "l", WireType::Long, static_cast<int64_t>(-1234567890123LL), "1");
        r.set_scalar(P + "ul", WireType::UnsignedLong, static_cast<uint64_t>(9876543210ULL), "1");
        r.set_scalar(P + "ll", WireType::LongLong, -9000000000000000000LL, "1");
        r.set_scalar(P + "ull", WireType::UnsignedLongLong, 18000000000000000000ULL, "1");
        r.set_scalar(P + "f", WireType::Float, 1.5f, "1");
        r.set_scalar(P + "d", WireType::Double, pi, "1");
        r.set_scalar(P + "b_true", WireType::Boolean, static_cast<uint8_t>(1), "1");
        r.set_scalar(P + "b_false", WireType::Boolean, static_cast<uint8_t>(0), "1");
        r.set_scalar(P + "wc", WireType::WideCharacter, static_cast<int32_t>(L'W'), "1");
        r.set_scalar(P + "color", WireType::Enumerated, static_cast<int32_t>(2), "1");
        r.set_scalar(P + "scoped", WireType::Enumerated, static_cast<int16_t>(-2), "1");

        // Floating-point edges and integer limits
        r.set_scalar(P + "d_neg", WireType::Double, -2.5, "1");
        r.set_scalar(P + "d_tiny", WireType::Double, 1.0e-300, "1");
        r.set_scalar(P + "d_huge", WireType::Double, 1.0e+300, "1");
        r.set_scalar(P + "d_third", WireType::Double, 1.0 / 3.0, "1");
        r.set_scalar(P + "d_inf", WireType::Double, std::numeric_limits<double>::infinity(), "1");
        r.set_scalar(P + "d_nan", WireType::Double, std::numeric_limits<double>::quiet_NaN(), "1");
        r.set_scalar(P + "f_third", WireType::Float, 1.0f / 3.0f, "1");
        r.set_scalar(P + "i32_min", WireType::Integer, INT_MIN, "1");
        r.set_scalar(P + "ull_max", WireType::UnsignedLongLong, ULLONG_MAX, "1");

        // Strings
        char carr[16] = "hello";
        r.set(P + "carr", FieldDesc::char_array(16), carr, "1");
        const char carr_full[8] = { 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H' };
        r.set(P + "carr_full", FieldDesc::char_array(8), carr_full, "1");
        add_text(r, P + "cptr", "c string");
        FieldDesc null_string = FieldDesc::array(WireType::String, 1, 0);
        null_string.text      = Text::Narrow;
        r.set(P + "cptr_null", null_string, nullptr, "1");
        add_text(r, P + "cptr_escape", "tab\there\nnew \"q\" \\ end");
        add_text(r, P + "str", "std string value");
        add_text(r, P + "str_empty", "");
        int32_t warr[8] = { 'w', 'i', 'd', 'e', 0, 0, 0, 0 };
        FieldDesc warr_desc = FieldDesc::array(WireType::WideCharacter, 4, 8);
        warr_desc.text      = Text::Wide;
        r.set(P + "warr", warr_desc, warr, "1");
        add_wide(r, P + "wptr", L"wptr!");

        // Arrays
        add_array<int32_t>(r, P + "iarr", WireType::Integer, { 10, 20, 30, 40, 50 });
        r.set_scalar(P + "iarr[2]", WireType::Integer, 30, "1");
        r.set_scalar(P + "iarr[4]", WireType::Integer, 50, "1");
        add_array<double>(r, P + "darr", WireType::Double, { 0, 0.5, 1, 1.5, 2, 2.5 }, "m");
        r.set_scalar(P + "darr[1][1]", WireType::Double, 1.5, "m");
        r.set_scalar(P + "darr[2][0]", WireType::Double, 2.0, "m");
        const unsigned char ucarr[4] = { 0, 1, 127, 255 };
        FieldDesc ucarr_desc         = FieldDesc::array(WireType::UnsignedCharacter, 1, 4);
        ucarr_desc.text              = Text::Narrow; // the old writer printed an unsigned char array as text
        r.set(P + "ucarr", ucarr_desc, ucarr, "1");
        r.set_scalar(P + "ucarr[3]", WireType::UnsignedCharacter, static_cast<unsigned char>(255), "1");
        add_array<uint8_t>(r, P + "barr", WireType::Boolean, { 1, 0, 1 });
        r.set_scalar(P + "barr[1]", WireType::Boolean, static_cast<uint8_t>(0), "1");
        std::vector<double> big(2000);
        for (int k = 0; k < 2000; ++k)
            big[k] = k + 0.25;
        add_array<double>(r, P + "big", WireType::Double, big);

        // Pointers: an unindexed pointer to numbers stages nothing.
        add_array<double>(r, P + "dptr", WireType::Double, {}, "m");
        r.set_scalar(P + "dptr[0]", WireType::Double, 0.5, "m");
        r.set_scalar(P + "dptr[1]", WireType::Double, 1.0, "m");
        r.set_scalar(P + "dptr[3]", WireType::Double, 2.0, "m");
        add_array<int32_t>(r, P + "iptr_null", WireType::Integer, {});
        r.set_scalar(P + "inner_ptr[0].a", WireType::Integer, 99, "1");
        r.set_scalar(P + "inner_ptr[0].b[1]", WireType::Double, -9.5, "m");

        // Structured
        r.set_scalar(P + "inner.a", WireType::Integer, 7, "1");
        add_array<double>(r, P + "inner.b", WireType::Double, { 1.25, -1.25 }, "m");
        r.set_scalar(P + "inner.b[1]", WireType::Double, -1.25, "m");
        // u3=5, u5=31, s4=-3, s12=1000 in one little-endian word; start as ICG writes it.
        const uint32_t word = 5u | (31u << 3) | (13u << 8) | (1000u << 12);
        add_bitfield(r, P + "bits.u3", WireType::UnsignedBitfield, word, 29, 3);
        add_bitfield(r, P + "bits.u5", WireType::UnsignedBitfield, word, 24, 5);
        add_bitfield(r, P + "bits.s4", WireType::Bitfield, word, 20, 4);
        add_bitfield(r, P + "bits.s12", WireType::Bitfield, word, 8, 12);

        // STL: elements, and containers that var_get_stl_size can size
        r.set_scalar(P + "vec[0]", WireType::Double, 1.5, "1");
        r.set_scalar(P + "vec[2]", WireType::Double, 3.5, "1");
        r.set_scalar(P + "deq[3]", WireType::Integer, 7, "1");
        r.set(P + "vec", FieldDesc::array(WireType::Stl, 1, 0), nullptr, "1")->stl_size = 3;
        r.set(P + "deq", FieldDesc::array(WireType::Stl, 1, 0), nullptr, "1")->stl_size = 4;
        r.set(P + "vec_empty", FieldDesc::array(WireType::Stl, 1, 0), nullptr, "1")->stl_size = 0;

        // Units
        r.set_scalar(P + "pos", WireType::Double, 1000.0, "m");
        r.set_scalar(P + "ang", WireType::Double, pi, "rad");
        r.set_scalar(P + "speed", WireType::Double, 10.0, "m/s");
        r.set_scalar(P + "temp", WireType::Double, 100.0, "degC");
        r.set_scalar(P + "count_m", WireType::Integer, 3, "m");
        FieldDesc unitless = FieldDesc::scalar(WireType::Double, 8);
        unitless.units_dashdash = true; // declared "--": ICG gives units "1"
        const double v42        = 42.0;
        r.set(P + "unitless", unitless, &v42, "1");
        r.set_scalar(P + "ratio", WireType::Double, 0.5, "1");

        // The session's "time" variable: sim time in seconds.
        r.set_scalar("time", WireType::Double, 0.0, "s");
    }

} // namespace vs_test

#endif
