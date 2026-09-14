// Independent pointer identity and pointee readback through the real MemoryManager.
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

    auto pointers(PointerModel& m)
    {
        return std::tie(m.enabled, m.text, m.signed_code, m.unsigned_code, m.small, m.unsigned_small, m.count,
                        m.unsigned_count, m.large, m.unsigned_large, m.huge, m.unsigned_huge, m.gain, m.position,
                        m.code);
    }

    template <typename Function, size_t... I> void each(Function function, std::index_sequence<I...>)
    {
        (function(std::integral_constant<size_t, I> { }), ...);
    }

    template <typename Function> void each(Function function)
    {
        each(function, std::make_index_sequence<std::tuple_size<Targets>::value> { });
    }

    bool same(PointerModel& m, PointerModel& expected, const Targets& targets, const Targets& saved)
    {
        bool equal = m.alias == expected.alias && m.tail == expected.tail && targets == saved;
        each(
            [&](auto index)
            {
                auto* actual   = std::get<index>(pointers(m));
                auto* original = std::get<index>(pointers(expected));
                if constexpr (index == 1 || index == 2)
                {
                    // Legacy TRICK_CHARACTER pointers restore string values into new
                    // storage, including signed char*. They do not preserve aliases.
                    equal = equal
                        && ((actual == nullptr && original == nullptr)
                            || (actual && original && actual != original
                                && std::strcmp(reinterpret_cast<const char*>(actual),
                                               reinterpret_cast<const char*>(original))
                                    == 0));
                }
                else
                    equal = equal && actual == original;
            });
        for (size_t i = 0; i < 2; ++i)
            for (size_t j = 0; j < 2; ++j)
                equal = equal && m.pairs[i][j] == expected.pairs[i][j];
        return equal;
    }

    int address(int* value, const PointerModel& m, const Targets& targets)
    {
        if (!value)
            return -1;
        if (value == &m.tail)
            return 3;
        for (int i = 0; i < 3; ++i)
            if (value == &std::get<6>(targets)[i])
                return i;
        throw std::runtime_error("unknown restored pointer address");
    }
}

int main()
{
    try
    {
        std::setlocale(LC_ALL, "C");
        PointerModel m { };
        Targets targets { };
        Trick::MemoryManager mm;
        probe::require(mm.declare_extern_var(&m, "PointerModel pointers") == &m, "pointer registration failed");
        const TRICK_TYPE kinds[] = { TRICK_BOOLEAN, TRICK_CHARACTER,      TRICK_CHARACTER,     TRICK_UNSIGNED_CHARACTER,
                                     TRICK_SHORT,   TRICK_UNSIGNED_SHORT, TRICK_INTEGER,       TRICK_UNSIGNED_INTEGER,
                                     TRICK_LONG,    TRICK_UNSIGNED_LONG,  TRICK_LONG_LONG,     TRICK_UNSIGNED_LONG_LONG,
                                     TRICK_FLOAT,   TRICK_DOUBLE,         TRICK_UNSIGNED_SHORT };
        each(
            [&](auto index)
            {
                auto& values = std::get<index>(targets);
                int extent   = 3;
                probe::require(mm.declare_extern_var(values.data(), kinds[index], "", 0,
                                                     "target_" + std::to_string(index), 1, &extent)
                                   == values.data(),
                               "target registration failed");
            });
        mm.set_reduced_checkpoint(false);
        // Pin the option whose production constructor fix is tracked separately.
        mm.set_hexfloat_decimal_comment_checkpoint(false);
        std::cout << "{\"round_trips\":[";
        for (int pass = 0; pass < 2; ++pass)
        {
            mm.set_expanded_arrays(pass == 1);
            mm.set_hexfloat_checkpoint(pass == 1);
            each(
                [&](auto index)
                {
                    auto& values                 = std::get<index>(targets);
                    using Value                  = typename std::decay_t<decltype(values)>::value_type;
                    values                       = { Value(17 + index + pass), Value(65 + index + pass), Value(0) };
                    std::get<index>(pointers(m)) = pass ? nullptr : &values[1];
                });
            m.alias          = pass ? &m.tail : m.count;
            m.pairs[0][0]    = &std::get<6>(targets)[0];
            m.pairs[0][1]    = &std::get<6>(targets)[1];
            m.pairs[1][0]    = nullptr;
            m.pairs[1][1]    = pass ? &m.tail : m.count;
            m.tail           = 101 + pass;
            auto expected    = m;
            const auto saved = targets;
            std::ostringstream checkpoint;
            mm.write_checkpoint(checkpoint);
            std::ofstream("checkpoint-" + std::to_string(pass) + ".txt") << checkpoint.str();
            each(
                [&](auto index)
                {
                    auto& values = std::get<index>(targets);
                    using Value  = typename std::decay_t<decltype(values)>::value_type;
                    values.fill(Value(0));
                    std::get<index>(pointers(m)) = &values[0];
                });
            m.alias = nullptr;
            for (auto& row : m.pairs)
                for (auto& value : row)
                    value = &m.tail;
            m.tail = -1;
            probe::require(!same(m, expected, targets, saved), "pointer control did not mutate storage");
            const int restored = mm.read_checkpoint_from_string(checkpoint.str().c_str());
            probe::require(restored == 0, "pointer checkpoint restore failed");
            probe::require(same(m, expected, targets, saved), "pointer checkpoint values did not round trip");
            if (pass)
                std::cout << ',';
            std::cout << '[';
            each(
                [&](auto index)
                {
                    if (index)
                        std::cout << ',';
                    const auto& values = std::get<index>(targets);
                    auto* value        = std::get<index>(pointers(m));
                    std::cout << '[';
                    if constexpr (index == 1 || index == 2)
                    {
                        if (value)
                            probe::quoted(reinterpret_cast<const char*>(value));
                        else
                            std::cout << "null";
                    }
                    else
                        std::cout << (value ? value - values.data() : -1);
                    for (const auto& item : values)
                        std::cout << ',' << +item;
                    std::cout << ']';
                });
            std::cout << ',' << address(m.alias, m, targets) << ",[";
            for (int i = 0; i < 2; ++i)
                for (int j = 0; j < 2; ++j)
                    std::cout << (i || j ? "," : "") << address(m.pairs[i][j], m, targets);
            std::cout << "]," << m.tail << ']';
        }
        std::cout << "]}\n";
        return 0;
    }
    catch (const std::exception& error)
    {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
