// Independent two-level address and terminal-value checkpoint observations.
#include "metadata.cpp"
#include "native_probe.hh"

#include "trick/MemoryManager.hh"

#include <array>
#include <clocale>
#include <fstream>
#include <sstream>
#include <tuple>

namespace
{
    using Targets
        = std::tuple<std::array<bool, 3>, std::array<char, 3>, std::array<signed char, 3>, std::array<unsigned char, 3>,
                     std::array<short, 3>, std::array<unsigned short, 3>, std::array<int, 3>,
                     std::array<unsigned int, 3>, std::array<long, 3>, std::array<unsigned long, 3>,
                     std::array<long long, 3>, std::array<unsigned long long, 3>, std::array<float, 3>,
                     std::array<double, 3>, std::array<char16_t, 3>>;
    template <size_t... I>
    auto slot_type(std::index_sequence<I...>)
        -> std::tuple<std::array<typename std::tuple_element_t<I, Targets>::value_type*, 3>...>;
    using Slots = decltype(slot_type(std::make_index_sequence<15> { }));
    auto pointers(DoublePointerModel& m)
    {
        return std::tie(m.enabled, m.text, m.signed_code, m.unsigned_code, m.small, m.unsigned_small, m.count,
                        m.unsigned_count, m.large, m.unsigned_large, m.huge, m.unsigned_huge, m.gain, m.position,
                        m.code);
    }
    template <class F, size_t... I> void each(F f, std::index_sequence<I...>)
    {
        (f(std::integral_constant<size_t, I> { }), ...);
    }
    template <class F> void each(F f) { each(f, std::make_index_sequence<15> { }); }
    bool same(DoublePointerModel& m, DoublePointerModel& expected, const Targets& targets, const Targets& saved,
              const Slots& slots, const Slots& saved_slots)
    {
        bool equal
            = targets == saved && m.tail == expected.tail && m.local == expected.local && m.alias == expected.alias;
        each(
            [&](auto index)
            {
                equal = equal && std::get<index>(pointers(m)) == std::get<index>(pointers(expected));
                for (size_t i = 0; i < 3; ++i)
                {
                    auto* actual   = std::get<index>(slots)[i];
                    auto* original = std::get<index>(saved_slots)[i];
                    if constexpr (index == 1 || index == 2)
                    {
                        // Legacy restores terminal TRICK_CHARACTER pointers as newly allocated strings.
                        equal = equal
                            && ((!actual && !original)
                                || (actual && original && actual != original
                                    && std::strcmp(reinterpret_cast<const char*>(actual),
                                                   reinterpret_cast<const char*>(original))
                                        == 0));
                    }
                    else
                        equal = equal && actual == original;
                }
                if constexpr (index == 1 || index == 2)
                    equal = equal && std::get<index>(slots)[0] != std::get<index>(slots)[1];
            });
        for (size_t i = 0; i < 2; ++i)
            for (size_t j = 0; j < 2; ++j)
                equal = equal && m.pairs[i][j] == expected.pairs[i][j];
        return equal;
    }
    int outer(int** p, DoublePointerModel& m, Slots& slots)
    {
        if (!p)
            return -1;
        if (p == &m.local)
            return 3;
        for (int i = 0; i < 3; ++i)
            if (p == &std::get<6>(slots)[i])
                return i;
        throw std::runtime_error("unknown outer pointer");
    }
}
int main()
{
    try
    {
        std::setlocale(LC_ALL, "C");
        DoublePointerModel m { };
        Targets targets { };
        Slots slots { };
        Trick::MemoryManager mm;
        probe::require(mm.declare_extern_var(&m, "DoublePointerModel model") == &m, "model registration");
        const TRICK_TYPE kinds[] = { TRICK_BOOLEAN, TRICK_CHARACTER,      TRICK_CHARACTER,     TRICK_UNSIGNED_CHARACTER,
                                     TRICK_SHORT,   TRICK_UNSIGNED_SHORT, TRICK_INTEGER,       TRICK_UNSIGNED_INTEGER,
                                     TRICK_LONG,    TRICK_UNSIGNED_LONG,  TRICK_LONG_LONG,     TRICK_UNSIGNED_LONG_LONG,
                                     TRICK_FLOAT,   TRICK_DOUBLE,         TRICK_UNSIGNED_SHORT };
        each(
            [&](auto index)
            {
                int extent   = 3;
                auto& values = std::get<index>(targets);
                auto& links  = std::get<index>(slots);
                probe::require(mm.declare_extern_var(values.data(), kinds[index], "", 0,
                                                     "target_" + std::to_string(index), 1, &extent)
                                   == values.data(),
                               "target registration");
                probe::require(mm.declare_extern_var(links.data(), kinds[index], "", 1,
                                                     "slots_" + std::to_string(index), 1, &extent)
                                   == links.data(),
                               "slot registration");
            });
        mm.set_reduced_checkpoint(false);
        mm.set_hexfloat_decimal_comment_checkpoint(false);
        std::cout << "{\"round_trips\":[";
        for (int pass = 0; pass < 2; ++pass)
        {
            mm.set_expanded_arrays(pass != 0);
            mm.set_hexfloat_checkpoint(pass != 0);
            each(
                [&](auto index)
                {
                    auto& values                 = std::get<index>(targets);
                    using Value                  = typename std::decay_t<decltype(values)>::value_type;
                    values                       = { Value(17 + index + pass), Value(65 + index + pass), Value(0) };
                    auto& links                  = std::get<index>(slots);
                    links                        = { &values[1], &values[1], nullptr };
                    std::get<index>(pointers(m)) = pass ? nullptr : &links[1];
                });
            m.tail                 = 101 + pass;
            m.local                = &m.tail;
            m.alias                = pass ? &m.local : m.count;
            m.pairs[0][0]          = &std::get<6>(slots)[0];
            m.pairs[0][1]          = &std::get<6>(slots)[2]; // nonnull outer, null inner
            m.pairs[1][0]          = nullptr;
            m.pairs[1][1]          = m.alias;
            auto expected          = m;
            const auto saved       = targets;
            const auto saved_slots = slots;
            std::ostringstream checkpoint;
            mm.write_checkpoint(checkpoint);
            std::ofstream("checkpoint-" + std::to_string(pass) + ".txt") << checkpoint.str();
            each(
                [&](auto index)
                {
                    auto& values = std::get<index>(targets);
                    using Value  = typename std::decay_t<decltype(values)>::value_type;
                    for (auto& value : values)
                        value = Value(!value);
                    auto& links                  = std::get<index>(slots);
                    links                        = { nullptr, nullptr, &values[0] };
                    std::get<index>(pointers(m)) = &links[0];
                });
            m.alias = nullptr;
            for (auto& row : m.pairs)
                for (auto& p : row)
                    p = &m.local;
            // pairs[1][1] may have pointed at m.local: use a different slot there.
            m.pairs[1][1] = &std::get<6>(slots)[2];
            m.local       = nullptr;
            m.tail        = -1;
            bool changed  = m.tail != expected.tail && m.local != expected.local && m.alias != expected.alias;
            each(
                [&](auto index)
                {
                    changed = changed && std::get<index>(pointers(m)) != std::get<index>(pointers(expected));
                    for (size_t i = 0; i < 3; ++i)
                        changed = changed && std::get<index>(targets)[i] != std::get<index>(saved)[i]
                            && std::get<index>(slots)[i] != std::get<index>(saved_slots)[i];
                });
            for (size_t i = 0; i < 2; ++i)
                for (size_t j = 0; j < 2; ++j)
                    changed = changed && m.pairs[i][j] != expected.pairs[i][j];
            probe::require(changed, "double pointer control did not mutate every location");
            const int restored = mm.read_checkpoint_from_string(checkpoint.str().c_str());
            probe::require(restored == 0, "double pointer checkpoint restore failed");
            probe::require(same(m, expected, targets, saved, slots, saved_slots),
                           "double pointer checkpoint values did not round trip");
            if (pass)
                std::cout << ',';
            std::cout << '[';
            each(
                [&](auto index)
                {
                    if (index)
                        std::cout << ',';
                    const auto& values = std::get<index>(targets);
                    const auto& links  = std::get<index>(slots);
                    auto p             = std::get<index>(pointers(m));
                    std::cout << '[' << (p ? p - links.data() : -1);
                    for (auto link : links)
                    {
                        std::cout << ',';
                        if constexpr (index == 1 || index == 2)
                        {
                            if (link)
                                probe::quoted(reinterpret_cast<const char*>(link));
                            else
                                std::cout << "null";
                        }
                        else
                            std::cout << (link ? link - values.data() : -1);
                    }
                    for (auto v : values)
                        std::cout << ',' << +v;
                    std::cout << ']';
                });
            std::cout << ',' << outer(m.alias, m, slots) << ",[";
            for (int i = 0; i < 2; ++i)
                for (int j = 0; j < 2; ++j)
                    std::cout << (i || j ? "," : "") << outer(m.pairs[i][j], m, slots);
            std::cout << "]," << m.tail << ',' << (m.local == &m.tail ? 0 : -1) << ']';
        }
        std::cout << "]}\n";
        return 0;
    }
    catch (const std::exception& e)
    {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
