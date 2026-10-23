// Phase 2 exit test: the new parser and encoders give the bytes of every
// golden capture of test/SIM_vs_conformance, with the variables modeled in
// ConformanceModel.hh. GoldenReplay.hh has the executor and the checks; the
// Phase 4 adapter test runs the same cases on the Memory Manager.

#include "ConformanceModel.hh"
#include "GoldenReplay.hh"
#include "UdunitsConverter.hh"

#include <memory>
#include <string>

#include <gtest/gtest.h>

using namespace vs_test;

namespace
{
    std::string run_on_model(const GoldenCase& gc, UnitConverter& units)
    {
        FakeResolver model;
        build_conformance_model(model);
        ConformanceResolver resolver(model);
        FakeClock clock; // time 0, as the SIM is frozen at 0
        return run_case(gc, resolver, units, &clock);
    }

    /** A converter that knows unit names but no conversions, when UDUNITS is not built in. */
    std::unique_ptr<UnitConverter> make_converter(bool* real)
    {
#ifdef VS_HAVE_UDUNITS
        auto u = std::make_unique<UdunitsConverter>();
        if (u->ok())
        {
            *real = true;
            return u;
        }
#endif
        *real   = false;
        auto f  = std::make_unique<FakeUnitConverter>();
        for (const char* n : { "m", "s", "1", "rad", "m/s", "degC" })
            f->add_name(n, n);
        return f;
    }

    class GoldenReplay : public ::testing::TestWithParam<GoldenCase>
    {
    };

} // namespace

TEST_P(GoldenReplay, MatchesTheCapture)
{
    const GoldenCase& gc = GetParam();
    bool real_units      = false;
    auto units           = make_converter(&real_units);
    const std::string why = case_precondition(gc, real_units);
    if (why == "python")
        return;
    if (!why.empty())
        GTEST_SKIP() << why;
    check_case_output(gc, run_on_model(gc, *units));
}

INSTANTIATE_TEST_SUITE_P(Conformance, GoldenReplay, ::testing::ValuesIn(golden_cases),
                         [](const ::testing::TestParamInfo<GoldenCase>& info) { return std::string(info.param.name); });

TEST(GoldenReplayCoverage, EveryCaseHasAGolden)
{
    for (const GoldenCase& gc : golden_cases)
        golden(gc.name);
    EXPECT_GE(sizeof golden_cases / sizeof golden_cases[0], 80u);
}
