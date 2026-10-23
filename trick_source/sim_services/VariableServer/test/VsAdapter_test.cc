// Phase 4 exit test: the adapter (MemoryResolver, Sampler, UdUnitsConverter)
// on a real Memory Manager holding the conformance SIM's own ConfVars.
//
// 1. Every golden case of test/SIM_vs_conformance runs through the parser,
//    the Memory Manager adapter and the encoders, and gives the captured
//    bytes (with the accepted fixes applied).
// 2. The scripts of the known-defect tests give the replies those tests
//    expect from the rewrite.
// 3. Unit tests for the staging plans, pointer validation, re-resolving,
//    STL sizes, units and the Sampler.
// 4. Phase 5: the golden cases through a real Session on the Memory Manager
//    (var_set included), and sessions copied on the main thread while
//    runners change their lists and memory is reloaded.

#include "GoldenReplay.hh"
#include "SessionHarness.hh"
#include "VsAdapterTypes.hh"

#include "trick/MemoryManager.hh"
#include "trick/UdUnits.hh"
#include "trick/memorymanager_c_intf.h"
#include "trick/vs/AsciiEncoder.hh"
#include "trick/vs/BinaryEncoder.hh"
#include "trick/vs/TimeVar.hh"
#include "trick/vs/adapter/MemoryResolver.hh"
#include "trick/vs/adapter/Sampler.hh"
#include "trick/vs/adapter/Server.hh"
#include "trick/vs/adapter/UdUnitsConverter.hh"
#include "trick/vs/SessionRegistry.hh"
#include "trick/vs/testing/Fakes.hh"

#include <atomic>
#include <chrono>
#include <cmath>
#include <thread>
#include <cstdlib>
#include <cstring>

#include <gtest/gtest.h>

using namespace Trick::vs;
using namespace Trick::vs::adapter;
using namespace vs_test;

namespace
{
    VsConfObject* conf = nullptr;

    /** One Memory Manager for the whole program, with the conformance variables, as in the SIM. */
    class ConformanceMemory : public ::testing::Environment
    {
        public:
            void SetUp() override
            {
                memory = new Trick::MemoryManager;
                units  = new Trick::UdUnits;
                ASSERT_EQ(units->read_default_xml(), 0);
                conf = static_cast<VsConfObject*>(TMM_declare_var_s("VsConfObject conf"));
                ASSERT_NE(conf, nullptr);
                conf->vars.default_vars();
                conf->vars.init();
            }

            Trick::MemoryManager* memory = nullptr;
            Trick::UdUnits* units        = nullptr;
    };

    ::testing::Environment* const environment = ::testing::AddGlobalTestEnvironment(new ConformanceMemory);

    const std::string P = "conf.vars.";

    /** Run a script with the adapter, as a session would. */
    std::string run_script(const std::string& script)
    {
        MemoryResolver resolver;
        UdUnitsConverter units;
        Trick::vs::testing::FakeClock clock;
        GoldenCase gc { "script", script.c_str(), false };
        return run_case(gc, resolver, units, &clock, [&](const std::function<void()>& stage) {
            auto lock = resolver.read_lock();
            stage();
        });
    }

    std::string be32(int32_t v)
    {
        std::string s;
        append_int32(s, v, true);
        return s;
    }

    std::string be_double(double d)
    {
        unsigned char b[8];
        std::memcpy(b, &d, 8);
        std::string s;
        for (int i = 7; i >= 0; --i)
            s += static_cast<char>(b[i]);
        return s;
    }

    /** Stage one name and return the snapshot. */
    Snapshot stage_one(MemoryResolver& resolver, const std::string& name, bool validate = false,
                       std::string* note = nullptr)
    {
        Snapshot s;
        auto var  = resolver.resolve(name);
        auto lock = resolver.read_lock();
        var->stage(s, validate);
        if (note)
            *note = static_cast<MemoryVar&>(*var).take_note();
        return s;
    }

    std::string ascii_of(const Snapshot& s)
    {
        std::string out;
        append_ascii_value(out, s.value(0).desc, s.data(0), nullptr, "");
        return out;
    }

    class AdapterGoldenReplay : public ::testing::TestWithParam<GoldenCase>
    {
    };
} // namespace

// ---------------------------------------------------------------------------
// 1. Golden replay on the Memory Manager
// ---------------------------------------------------------------------------

TEST_P(AdapterGoldenReplay, MatchesTheCapture)
{
    const GoldenCase& gc  = GetParam();
    const std::string why = case_precondition(gc, true);
    if (why == "python")
        return;
    if (!why.empty())
        GTEST_SKIP() << why;
    check_case_output(gc, run_script(gc.script));
}

INSTANTIATE_TEST_SUITE_P(Conformance, AdapterGoldenReplay, ::testing::ValuesIn(golden_cases),
                         [](const ::testing::TestParamInfo<GoldenCase>& info) { return std::string(info.param.name); });

// ---------------------------------------------------------------------------
// 2. The known-defect scripts give the replies their tests expect
// ---------------------------------------------------------------------------

TEST(AdapterFixedDefects, LongStringIsStagedWhole)
{
    // Phase 0: the 4096-byte stage buffer overflowed. Under ASan this test also
    // shows no memory error.
    EXPECT_EQ(run_script("trick.var_add(\"" + P + "str_long\")\ntrick.var_send()\n"),
              "0\t" + std::string(5000, 'x') + "\n");
}

TEST(AdapterFixedDefects, CharArrayWithNoNul)
{
    EXPECT_EQ(run_script("trick.var_add(\"" + P + "carr_full\")\ntrick.var_send()\n"), "0\tABCDEFGH\n");
}

TEST(AdapterFixedDefects, ShortEnum)
{
    EXPECT_EQ(run_script("trick.var_add(\"" + P + "scoped\")\ntrick.var_send()\n"), "0\t-2\n");
}

TEST(AdapterFixedDefects, ByteswapIndexedElement)
{
    // Phase 0: byteswap swapped the declared array length past one element.
    const std::string reply = run_script("trick.var_binary_nonames()\ntrick.var_byteswap(True)\ntrick.var_add(\"" + P
                                         + "iarr[2]\")\ntrick.var_add(\"" + P + "darr[1][1]\")\ntrick.var_send()\n");
    EXPECT_EQ(reply, be32(0) + be32(12 + 12 + 16 - 4) + be32(2) + be32(6) + be32(4) + be32(30) + be32(11) + be32(8)
                         + be_double(1.5));
}

TEST(AdapterFixedDefects, ByteswapStrings)
{
    const std::string reply = run_script("trick.var_binary_nonames()\ntrick.var_byteswap(True)\ntrick.var_add(\"" + P
                                         + "str\")\ntrick.var_add(\"" + P + "wptr\")\ntrick.var_send()\n");
    const std::string text("std string value\0", 17);
    std::string wide;
    for (char c : std::string("wptr!"))
        wide += be32(c);
    wide += be32(0);
    const std::string body = be32(3) + be32(static_cast<int32_t>(text.size())) + text + be32(19)
                           + be32(static_cast<int32_t>(wide.size())) + wide;
    EXPECT_EQ(reply, be32(0) + be32(static_cast<int32_t>(12 + body.size() - 4)) + be32(2) + body);
}

TEST(AdapterFixedDefects, ByteswapPointerElementAndBitfield)
{
    EXPECT_EQ(run_script("trick.var_binary_nonames()\ntrick.var_byteswap(True)\ntrick.var_add(\"" + P
                         + "dptr[3]\")\ntrick.var_send()\n"),
              be32(0) + be32(12 + 16 - 4) + be32(1) + be32(11) + be32(8) + be_double(2.0));
    EXPECT_EQ(run_script("trick.var_binary_nonames()\ntrick.var_byteswap(True)\ntrick.var_add(\"" + P
                         + "bits.s4\")\ntrick.var_send()\n"),
              be32(0) + be32(12 + 12 - 4) + be32(1) + be32(12) + be32(4) + be32(-3));
}

TEST(AdapterFixedDefects, CharArrayThroughVectorOfPointers)
{
    // Phase 0: the old server sent the first character.
    EXPECT_EQ(run_script("trick.var_add(\"" + P + "label_ptrs[1].text\")\ntrick.var_send()\n"), "0\tlabel 1\n");
}

TEST(AdapterFixedDefects, UnindexedPointerStagesItsArray)
{
    // Phase 4: the old server asked get_size() about the pointer's own address.
    EXPECT_EQ(run_script("trick.var_add(\"" + P + "dptr\")\ntrick.var_send()\n"), "0\t0.5,1,1.5,2\n");
    EXPECT_EQ(run_script("trick.var_add(\"" + P + "iptr_null\")\ntrick.var_send()\n"), "0\t\n");
}

// ---------------------------------------------------------------------------
// 3. Staging plans
// ---------------------------------------------------------------------------

namespace
{
    StagePlan plan_of(const std::string& name)
    {
        RefPtr ref = resolve_ref(name);
        return make_plan(ref.get());
    }

    /** `d` for a variable declared with "--" units, as most ConfVars members are. */
    FieldDesc dashdash(FieldDesc d)
    {
        d.units_dashdash = true;
        return d;
    }
} // namespace

TEST(StagePlan, Scalars)
{
    auto i = plan_of(P + "i32");
    EXPECT_EQ(i.source, StagePlan::Source::Memory);
    EXPECT_EQ(i.desc, dashdash(FieldDesc::scalar(WireType::Integer, 4)));
    EXPECT_FALSE(i.follow_path);
    EXPECT_FALSE(i.resolve_each_copy);

    auto e = plan_of(P + "scoped");
    EXPECT_EQ(e.desc.type, WireType::Enumerated);
    EXPECT_EQ(e.desc.element_size, 2u); // its real size

    auto b = plan_of(P + "bits.s4");
    EXPECT_EQ(b.desc.type, WireType::Bitfield);
    EXPECT_EQ(b.desc.bitfield.start, 20);
    EXPECT_EQ(b.desc.bitfield.width, 4);

    EXPECT_TRUE(plan_of(P + "unitless").desc.units_dashdash);
    EXPECT_FALSE(plan_of(P + "pos").desc.units_dashdash);
}

TEST(StagePlan, ArraysAndText)
{
    EXPECT_EQ(plan_of(P + "iarr").desc, dashdash(FieldDesc::array(WireType::Integer, 4, 5)));
    EXPECT_EQ(plan_of(P + "darr").desc, FieldDesc::array(WireType::Double, 8, 6));
    EXPECT_EQ(plan_of(P + "darr[1]").desc, FieldDesc::array(WireType::Double, 8, 2));
    auto carr = plan_of(P + "carr");
    EXPECT_EQ(carr.desc.text, Text::Narrow);
    EXPECT_EQ(carr.desc.count, 16u);
    auto warr = plan_of(P + "warr");
    EXPECT_EQ(warr.desc.type, WireType::WideCharacter);
    EXPECT_EQ(warr.desc.text, Text::Wide);
    EXPECT_EQ(plan_of(P + "ucarr").desc.text, Text::Narrow);
}

TEST(StagePlan, StringsAndPointers)
{
    EXPECT_EQ(plan_of(P + "str").source, StagePlan::Source::StdString);
    EXPECT_EQ(plan_of(P + "cptr").source, StagePlan::Source::CharPointer);
    EXPECT_EQ(plan_of(P + "wptr").source, StagePlan::Source::WCharPointer);
    EXPECT_EQ(plan_of(P + "dptr").source, StagePlan::Source::Pointer);
    auto element = plan_of(P + "dptr[1]");
    EXPECT_EQ(element.source, StagePlan::Source::Memory);
    EXPECT_TRUE(element.follow_path);
}

TEST(StagePlan, CompositesAndUnknownNames)
{
    EXPECT_EQ(plan_of(P + "inner").source, StagePlan::Source::NoValue);
    EXPECT_EQ(plan_of(P + "bits").source, StagePlan::Source::NoValue);
    EXPECT_EQ(plan_of(P + "no_such_member").source, StagePlan::Source::BadRef);
    EXPECT_EQ(plan_of("no_such_object.x").source, StagePlan::Source::BadRef);
    EXPECT_FALSE(plan_of(P + "no_such_member").note.empty());
}

TEST(StagePlan, StlPathsAreResolvedEachCopy)
{
    auto v = plan_of(P + "vec[1]");
    EXPECT_EQ(v.source, StagePlan::Source::Memory);
    EXPECT_EQ(v.desc, dashdash(FieldDesc::scalar(WireType::Double, 8)));
    EXPECT_TRUE(v.resolve_each_copy);
    auto label = plan_of(P + "label_ptrs[1].text");
    EXPECT_TRUE(label.resolve_each_copy);
    EXPECT_EQ(label.desc.count, 16u);
    EXPECT_EQ(label.desc.text, Text::Narrow);
}

TEST(StagePlan, EveryConformanceVariableHasAValidDescription)
{
    for (const char* n : { "c", "sc", "uc", "s", "us", "i32", "u32", "l", "ul", "ll", "ull", "f", "d", "b_true", "wc",
                           "color", "scoped", "carr", "carr_full", "iarr", "darr", "ucarr", "barr", "big", "pos",
                           "bits.u3", "bits.u5", "bits.s4", "bits.s12", "inner.a", "inner.b", "vec[0]", "deq[3]" })
    {
        auto p = plan_of(P + n);
        EXPECT_EQ(p.source, StagePlan::Source::Memory) << n;
        EXPECT_EQ(validate(p.desc), nullptr) << n;
    }
}

TEST(StagePlan, WireTypesAreTrickTypes)
{
    EXPECT_EQ(wire_type(TRICK_DOUBLE), WireType::Double);
    EXPECT_EQ(wire_type(TRICK_STL), WireType::Stl);
    EXPECT_EQ(wire_type(TRICK_NUMBER_OF_TYPES), WireType::BadRef);
    EXPECT_EQ(wire_type(-1), WireType::BadRef);
}

// ---------------------------------------------------------------------------
// Staging: pointers, validation, re-resolving
// ---------------------------------------------------------------------------

TEST(MemoryVar, NullPointerOnThePathIsBadRefThisCopy)
{
    MemoryResolver resolver;
    auto var        = resolver.resolve(P + "dptr[1]");
    double* saved   = conf->vars.dptr;
    conf->vars.dptr = nullptr;
    Snapshot s;
    {
        auto lock = resolver.read_lock();
        var->stage(s, false);
    }
    conf->vars.dptr = saved;
    EXPECT_TRUE(s.value(0).desc.is_bad_ref());
    EXPECT_NE(static_cast<MemoryVar&>(*var).take_note().find("NULL"), std::string::npos);

    // The pointer is back: the next copy has the value again.
    Snapshot again;
    {
        auto lock = resolver.read_lock();
        var->stage(again, false);
    }
    EXPECT_EQ(ascii_of(again), "1");
}

TEST(MemoryVar, ValidateAddressRefusesMemoryTheMemoryManagerDoesNotKnow)
{
    // The old var_validate_address did nothing (Phase 0).
    MemoryResolver resolver;
    double* outside = static_cast<double*>(std::malloc(4 * sizeof(double)));
    for (int k = 0; k < 4; ++k)
        outside[k] = 100.0 + k;
    double* saved   = conf->vars.dptr;
    conf->vars.dptr = outside;

    std::string note;
    Snapshot unchecked = stage_one(resolver, P + "dptr[1]", false);
    Snapshot checked   = stage_one(resolver, P + "dptr[1]", true, &note);
    conf->vars.dptr    = saved;
    std::free(outside);

    EXPECT_EQ(ascii_of(unchecked), "101");
    EXPECT_TRUE(checked.value(0).desc.is_bad_ref());
    EXPECT_NE(note.find("does not know"), std::string::npos) << note;
    // Memory the Memory Manager knows passes.
    EXPECT_EQ(ascii_of(stage_one(resolver, P + "dptr[1]", true)), "1");
}

TEST(MemoryVar, StlElementIsFoundAgainAfterTheContainerMoves)
{
    // The old server kept the first address; after a reallocation it read freed
    // memory (ASan shows it).
    MemoryResolver resolver;
    auto var = resolver.resolve(P + "vec[2]");
    conf->vars.vec.reserve(conf->vars.vec.capacity() * 8 + 64); // moves the elements
    Snapshot s;
    {
        auto lock = resolver.read_lock();
        var->stage(s, false);
    }
    EXPECT_EQ(ascii_of(s), "3.5");
    conf->vars.vec.shrink_to_fit();
}

TEST(MemoryVar, UnresolvedNameIsTriedAgainEachCopy)
{
    MemoryResolver resolver;
    auto var = resolver.resolve(P + "vec[3]");
    EXPECT_FALSE(var->resolved());
    EXPECT_TRUE(stage_one(resolver, P + "vec[3]").value(0).desc.is_bad_ref());
    conf->vars.vec.push_back(4.5);
    Snapshot s;
    {
        auto lock = resolver.read_lock();
        var->stage(s, false);
    }
    conf->vars.vec.pop_back();
    EXPECT_EQ(ascii_of(s), "4.5");
}

TEST(MemoryVar, CompositeIsNeverTriedAgain)
{
    MemoryResolver resolver;
    auto var = resolver.resolve(P + "inner");
    EXPECT_TRUE(var->resolved()); // var_exists says it exists
    Snapshot s;
    {
        auto lock = resolver.read_lock();
        var->stage(s, false);
    }
    EXPECT_TRUE(s.value(0).desc.is_bad_ref());
}

TEST(MemoryVar, NewMemoryEpochResolvesAgain)
{
    MemoryResolver resolver;
    auto var             = resolver.resolve(P + "i32");
    const uint64_t first = var->epoch();
    EXPECT_EQ(first, resolver.memory_epoch());
    {
        auto lock = resolver.write_lock();
        resolver.memory_replaced();
    }
    EXPECT_NE(var->epoch(), resolver.memory_epoch());
    Snapshot s;
    {
        auto lock = resolver.read_lock();
        var->stage(s, false);
    }
    EXPECT_EQ(var->epoch(), resolver.memory_epoch());
    EXPECT_EQ(ascii_of(s), "-123456789");
}

TEST(MemoryVar, StlSize)
{
    MemoryResolver resolver;
    EXPECT_EQ(resolver.resolve(P + "vec")->stl_size(), std::optional<int64_t>(3));
    EXPECT_EQ(resolver.resolve(P + "deq")->stl_size(), std::optional<int64_t>(4));
    EXPECT_EQ(resolver.resolve(P + "vec_empty")->stl_size(), std::optional<int64_t>(0));
    EXPECT_FALSE(resolver.resolve(P + "i32")->stl_size());
    EXPECT_FALSE(resolver.resolve(P + "vec[0]")->stl_size()); // an element, not the container
    EXPECT_FALSE(resolver.resolve(P + "no_such_member")->stl_size());
}

TEST(MemoryVar, BaseUnits)
{
    MemoryResolver resolver;
    EXPECT_EQ(resolver.resolve(P + "pos")->base_units(), "m");
    EXPECT_EQ(resolver.resolve(P + "unitless")->base_units(), "1");
    EXPECT_EQ(resolver.resolve(P + "no_such_member")->base_units(), "");
}

// ---------------------------------------------------------------------------
// Units and the Sampler
// ---------------------------------------------------------------------------

TEST(UdUnitsConverter, ConversionsAndNames)
{
    UdUnitsConverter units;
    auto ft = units.converter("m", "ft");
    ASSERT_TRUE(ft);
    ASSERT_TRUE(ft.value());
    EXPECT_NEAR(ft.value()->apply(1000.0), 3280.839895013123, 1e-9);
    auto same = units.converter("m", "m");
    ASSERT_TRUE(same);
    EXPECT_FALSE(same.value()); // the identity: no conversion
    EXPECT_FALSE(units.converter("m", "s"));
    EXPECT_FALSE(units.converter("m", "not_a_unit"));
    EXPECT_EQ(units.canonical("M").value(), "m"); // an old Trick name
    EXPECT_EQ(units.canonical("d").value(), "degree");
    EXPECT_FALSE(units.canonical("not_a_unit"));
}

TEST(Sampler, StagesInOrderWithTheTime)
{
    MemoryResolver resolver;
    Trick::vs::testing::FakeClock clock;
    clock.time            = 2500000;
    clock.tics_per_second = 1000000;
    Sampler sampler(resolver, clock);
    std::vector<std::unique_ptr<ResolvedVar>> vars;
    vars.push_back(resolver.resolve(P + "i32"));
    vars.push_back(std::make_unique<TimeVar>());
    vars.push_back(resolver.resolve(P + "no_such_member"));
    Snapshot s;
    sampler.sample(s, vars, false);
    ASSERT_EQ(s.size(), 3u);
    EXPECT_EQ(s.sequence, 1u);
    EXPECT_EQ(s.time_tics, 2500000);
    EXPECT_DOUBLE_EQ(s.time_s, 2.5);
    std::string text;
    append_ascii_value(text, s.value(1).desc, s.data(1), nullptr, "s");
    EXPECT_EQ(text, "2.5 {s}");
    EXPECT_TRUE(s.value(2).desc.is_bad_ref());
    sampler.sample(s, vars, false);
    EXPECT_EQ(s.size(), 3u); // cleared first
    EXPECT_EQ(s.sequence, 2u);
}

TEST(Sampler, ConcurrentCopiesAndMemoryReloads)
{
    // Phase 5 samples from the main thread and from session runners while a
    // checkpoint load may replace memory. Under TSan this shows whether the
    // staging path, the epoch and ref_attributes() race.
    MemoryResolver resolver;
    Trick::vs::testing::FakeClock clock;
    Sampler sampler(resolver, clock);
    std::atomic<bool> stop { false };
    std::atomic<int> copies { 0 };

    auto copier = [&] {
        std::vector<std::unique_ptr<ResolvedVar>> vars;
        for (const char* n : { "i32", "d", "str", "dptr[1]", "vec[1]", "label_ptrs[0].text", "no_such_member" })
            vars.push_back(resolver.resolve(P + n));
        Snapshot s;
        while (!stop)
        {
            sampler.sample(s, vars, false);
            EXPECT_EQ(s.size(), vars.size());
            ++copies;
        }
    };
    std::thread a(copier);
    std::thread b(copier);
    for (int i = 0; i < 50; ++i)
    {
        {
            auto lock = resolver.write_lock();
            resolver.memory_replaced();
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    stop = true;
    a.join();
    b.join();
    EXPECT_GT(copies.load(), 0);
}

// ---------------------------------------------------------------------------
// 4. Phase 5: sessions on the Memory Manager
// ---------------------------------------------------------------------------

namespace
{
    /** A FakeHost that reads memory under the resolver's lock and writes with the real var_set. */
    class MemoryHost : public FakeHost
    {
        public:
            explicit MemoryHost(MemoryResolver& r)
                : resolver(r)
            {
                memory = [this](const std::function<void()>& read) {
                    auto lock = lock_shared_releasing_gil(resolver.memory_mutex());
                    read();
                };
            }

            int var_set(const cmd::VarSet& c) override
            {
                auto lock = lock_shared_releasing_gil(resolver.memory_mutex());
                return assign_variable(c.name.c_str(), c.value, c.units ? c.units->c_str() : nullptr);
            }

            MemoryResolver& resolver;
    };

    class SessionOnMemory : public ::testing::TestWithParam<GoldenCase>
    {
    };
} // namespace

TEST_P(SessionOnMemory, MatchesTheCapture)
{
    const GoldenCase& gc  = GetParam();
    const std::string why = case_precondition(gc, true);
    if (why == "python")
        return;
    if (!why.empty() && why.rfind("var_set", 0) != 0) // var_set runs here: it has a real Memory Manager
        GTEST_SKIP() << why;
    MemoryResolver resolver;
    UdUnitsConverter units;
    Trick::vs::testing::FakeClock clock;
    MemoryHost host(resolver);
    check_case_output(gc, run_case_in_session(gc, resolver, units, clock, host));
}

INSTANTIATE_TEST_SUITE_P(Conformance, SessionOnMemory, ::testing::ValuesIn(golden_cases),
                         [](const ::testing::TestParamInfo<GoldenCase>& info) { return std::string(info.param.name); });

TEST(SessionOnMemory, VarSetCodesMatchTheOldServer)
{
    MemoryResolver resolver;
    auto lock = resolver.read_lock();
    EXPECT_EQ(assign_variable((P + "settable").c_str(), cmd::SetValue(7LL), nullptr), 0);
    EXPECT_EQ(conf->vars.settable, 7);
    EXPECT_EQ(assign_variable((P + "read_only").c_str(), cmd::SetValue(1LL), nullptr), 1);
    EXPECT_EQ(assign_variable((P + "no_such_member").c_str(), cmd::SetValue(1LL), nullptr), 2);
    EXPECT_EQ(assign_variable((P + "settable_d").c_str(), cmd::SetValue(150.0), "cm"), 0);
    EXPECT_DOUBLE_EQ(conf->vars.settable_d, 1.5);
    EXPECT_EQ(assign_variable((P + "settable_str").c_str(), cmd::SetValue(std::string("x")), nullptr), 0);
    EXPECT_EQ(conf->vars.settable_str, "x");
    // Put the values back for the other tests.
    EXPECT_EQ(assign_variable((P + "settable").c_str(), cmd::SetValue(12LL), nullptr), 0);
    EXPECT_EQ(assign_variable((P + "settable_d").c_str(), cmd::SetValue(2.0), nullptr), 0);
    EXPECT_EQ(assign_variable((P + "settable_str").c_str(), cmd::SetValue(std::string("before")), nullptr), 0);
}

TEST(SessionOnMemory, AnStlElementFollowsTheVectorAcrossCopies)
{
    MemoryResolver resolver;
    UdUnitsConverter units;
    Trick::vs::testing::FakeClock clock;
    MemoryHost host(resolver);
    StringOutput out;
    Session session(host, resolver, units, clock, clock, out, SessionConfig {});
    session.handle_batch("trick.var_pause()\ntrick.var_add(\"conf.vars.vec[0]\")\ntrick.var_send()\n");
    EXPECT_EQ(out.take(), "0\t1.5\n");
    const std::vector<double> saved = conf->vars.vec;
    {
        auto lock = resolver.write_lock(); // as the main thread holds it while models run
        conf->vars.grow_vec(4096, 42.0);
    }
    session.handle_batch("trick.var_send()\n");
    EXPECT_EQ(out.take(), "0\t42\n");
    auto lock      = resolver.write_lock();
    conf->vars.vec = saved;
}

TEST(SessionOnMemory, MainThreadCopiesRunnerChangesAndReloads)
{
    // The Phase 5 thread split on a real Memory Manager. Under TSan (with the
    // Memory Manager compiled with TSan too) this shows races between the
    // main thread's copies, a runner that changes its list and sends, and a
    // checkpoint reload taking the memory lock.
    MemoryResolver resolver;
    UdUnitsConverter units;
    Trick::vs::testing::FakeClock clock;
    clock.is_real_time = true;
    MemoryHost host(resolver);
    StringOutput out;
    auto session = std::make_shared<Session>(host, resolver, units, clock, clock, out, SessionConfig {});
    std::atomic<int> wakes { 0 };
    session->set_waker([&] { ++wakes; });
    SessionRegistry registry;
    registry.add(session);
    session->handle_batch("trick.var_add(\"conf.vars.i32\")\ntrick.var_add(\"conf.vars.vec[1]\")\n"
                          "trick.var_set_copy_mode(2)\ntrick.var_set_write_mode(1)\n");

    std::atomic<bool> stop { false };
    std::atomic<long long> frames { 0 };
    std::thread main_thread([&] {
        long long frame = 0;
        while (!stop)
        {
            registry.refresh(frame, 0);
            registry.copy_top(frame);
            registry.copy_scheduled(frame * 1000);
            if (frame % 200 == 199)
            {
                auto lock = resolver.write_lock(); // a checkpoint reload
                resolver.memory_replaced();
            }
            ++frame;
            ++frames;
        }
    });
    const char* names[] = { "conf.vars.d", "conf.vars.str", "conf.vars.label_ptrs[0].text", "conf.vars.dptr" };
    for (int i = 0; i < 400; ++i)
    {
        const std::string n = names[i % 4];
        session->handle_batch(i % 2 ? "trick.var_remove(\"" + n + "\")\n" : "trick.var_add(\"" + n + "\")\n");
        if (i % 25 == 0)
            session->handle_batch("trick.var_set_copy_mode(" + std::to_string(i % 3) + ")\ntrick.var_send()\n");
        session->on_wake();
        session->on_deadline();
        out.take();
    }
    stop = true;
    main_thread.join();
    EXPECT_GT(frames.load(), 0);
    EXPECT_FALSE(session->exiting());
}
