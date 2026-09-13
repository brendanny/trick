// Independent ordinary enum storage and symbolic checkpoint observations.
#include "metadata.cpp"
#include "native_probe.hh"

#include "trick/MemoryManager.hh"

#include <clocale>
#include <fstream>
#include <sstream>
#include <tuple>

namespace
{
    template <class T> auto members(T& record)
    {
        if constexpr (std::is_same<typename std::remove_cv<T>::type, EnumRecord>::value)
            return std::tie(record.lead, record.state, record.phase, record.states, record.phases, record.mode,
                            record.tail);
        else
            return std::tie(record.mode, record.pairs, record.repeated);
    }
    template <class T> bool equal(const T& a, const T& b)
    {
        if constexpr (std::is_array<T>::value)
        {
            for (size_t i = 0; i < std::extent<T>::value; ++i)
                if (!equal(a[i], b[i]))
                    return false;
            return true;
        }
        else
            return a == b;
    }
    template <class T, size_t... I> bool same(const T& a, const T& b, std::index_sequence<I...>)
    {
        return (equal(std::get<I>(members(a)), std::get<I>(members(b))) && ...);
    }
    template <class T> bool same(const T& a, const T& b)
    {
        return same(a, b, std::make_index_sequence<std::tuple_size<decltype(members(a))>::value> { });
    }
    template <class T> void corrupt(T& field)
    {
        if constexpr (std::is_array<T>::value)
            for (auto& item : field)
                corrupt(item);
        else
            field = static_cast<T>(1);
    }
    template <class T> void corrupt_record(T& record)
    {
        std::apply([](auto&... field) { (corrupt(field), ...); }, members(record));
    }
    template <class T> void print(const T& field)
    {
        if constexpr (std::is_array<T>::value)
        {
            std::cout << '[';
            for (size_t i = 0; i < std::extent<T>::value; ++i)
            {
                if (i)
                    std::cout << ',';
                print(field[i]);
            }
            std::cout << ']';
        }
        else if constexpr (std::is_enum<T>::value)
            std::cout << static_cast<long long>(field);
        else
            std::cout << field;
    }
    template <class T> void print_record(const T& record, bool& first)
    {
        auto item = [&first](const auto& value)
        {
            if (!first)
                std::cout << ',';
            first = false;
            print(value);
        };
        std::apply([&item](const auto&... field) { (item(field), ...); }, members(record));
    }
}

int main()
{
    try
    {
        probe::require(std::setlocale(LC_ALL, "C") != nullptr, "C locale unavailable");
        EnumRecord record { };
        record_enum::Aliases aliases { };
        Trick::MemoryManager mm;
        probe::require(mm.declare_extern_var(&record, "EnumRecord record") == &record, "record registration");
        probe::require(mm.declare_extern_var(&aliases, "record_enum__Aliases aliases") == &aliases,
                       "namespace record registration");
        mm.set_reduced_checkpoint(false);
        mm.set_hexfloat_checkpoint(false);
        mm.set_hexfloat_decimal_comment_checkpoint(false);
        for (const auto& item : {
                 std::pair<const char*, int> { "state_negative",         -3         },
                 { "state_zero",             0          },
                 { "state_maximum",          2147483647 },
                 { "phase_idle",             0          },
                 { "phase_running",          2          },
                 { "phase_alias",            2          },
                 { "record_enum::mode_zero", 0          },
                 { "record_enum::mode_high", 2147483647 }
        })
        {
            V_DATA value { };
            probe::require(mm.get_enumerated(item.first, &value) == 0 && value.type == TRICK_ENUMERATED
                               && value.value.i == item.second,
                           "enum lookup differs");
        }
        std::cout << "{\"round_trips\":[";
        for (int pass = 0; pass < 2; ++pass)
        {
            mm.set_expanded_arrays(pass != 0);
            // Named values, duplicate-valued labels and unnamed numeric values.
            record = {
                42 + pass,
                state_negative,
                RecordPhase::phase_alias,
                { state_zero, state_maximum, static_cast<RecordState>(-19 - pass) },
                { { RecordPhase::phase_idle, RecordPhase::phase_running },
                               { static_cast<RecordPhase>(42 + pass), static_cast<RecordPhase>(-4 - pass) } },
                record_enum::Mode::mode_high,
                1.25 + pass
            };
            aliases = {
                static_cast<record_enum::Mode>(23 + pass),
                { { RecordPhase::phase_idle, RecordPhase::phase_alias },
                                                { static_cast<RecordPhase>(19 + pass), static_cast<RecordPhase>(-7 - pass) } },
                state_maximum
            };
            const auto expected_record  = record;
            const auto expected_aliases = aliases;
            std::ostringstream checkpoint;
            mm.write_checkpoint(checkpoint);
            std::ofstream(std::string("checkpoint-") + std::to_string(pass) + ".txt") << checkpoint.str();
            const auto text = checkpoint.str();
            probe::require(text.find("state_negative") != std::string::npos
                               && text.find("phase_running") != std::string::npos
                               && text.find("record_enum::mode_high") != std::string::npos
                               && text.find("phase_alias") == std::string::npos,
                           "symbolic enum checkpoint differs");
            corrupt_record(record);
            corrupt_record(aliases);
            probe::require(!same(record, expected_record) && !same(aliases, expected_aliases),
                           "enum control did not mutate storage");
            const int restored = mm.read_checkpoint_from_string(checkpoint.str().c_str());
            probe::require(restored == 0, "enum checkpoint restore failed");
            probe::require(same(record, expected_record) && same(aliases, expected_aliases),
                           "ordinary enum checkpoint values did not round trip");
            if (pass)
                std::cout << ',';
            std::cout << '[';
            bool first = true;
            print_record(record, first);
            print_record(aliases, first);
            std::cout << ']';
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
