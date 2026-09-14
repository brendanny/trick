// Independent enum pointer identity, symbolic values and checkpoint readback.
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
        if constexpr (std::is_same<std::remove_cv_t<T>, EnumPointerModel>::value)
            return std::tie(record.lead, record.state, record.phase, record.mode, record.alias, record.states,
                            record.matrix, record.local, record.tail);
        else
            return std::tie(record.states, record.phases, record.modes);
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

    template <class T> int address(T* value, const EnumPointerModel& model, const enum_pointer::Targets& targets)
    {
        if (!value)
            return -1;
        if constexpr (std::is_same<T, PointerState>::value)
            if (value == &model.local)
                return 3;
        for (int i = 0; i < 3; ++i)
        {
            if constexpr (std::is_same<T, PointerState>::value)
            {
                if (value == &targets.states[i])
                    return i;
            }
            else if constexpr (std::is_same<T, PointerPhase>::value)
            {
                if (value == &targets.phases[i])
                    return i;
            }
            else
            {
                if (value == &targets.modes[i])
                    return i;
            }
        }
        throw std::runtime_error("unknown restored enum target");
    }

    template <class T> void print(const T& field, const EnumPointerModel& model, const enum_pointer::Targets& targets)
    {
        if constexpr (std::is_array<T>::value)
        {
            std::cout << '[';
            for (size_t i = 0; i < std::extent<T>::value; ++i)
            {
                if (i)
                    std::cout << ',';
                print(field[i], model, targets);
            }
            std::cout << ']';
        }
        else if constexpr (std::is_pointer<T>::value)
            std::cout << address(field, model, targets);
        else
            std::cout << static_cast<long long>(field);
    }
}

int main()
{
    try
    {
        probe::require(std::setlocale(LC_ALL, "C") != nullptr, "C locale unavailable");
        EnumPointerModel model { };
        enum_pointer::Targets targets { };
        Trick::MemoryManager mm;
        probe::require(mm.declare_extern_var(&model, "EnumPointerModel model") == &model, "model registration");
        probe::require(mm.declare_extern_var(&targets, "enum_pointer__Targets targets") == &targets,
                       "target registration");
        mm.set_reduced_checkpoint(false);
        mm.set_hexfloat_checkpoint(false);
        mm.set_hexfloat_decimal_comment_checkpoint(false);
        for (const auto& item : {
                 std::pair<const char*, int> { "pointer_negative",                -3         },
                 { "pointer_zero",                    0          },
                 { "pointer_maximum",                 2147483647 },
                 { "pointer_idle",                    0          },
                 { "pointer_running",                 2          },
                 { "pointer_alias",                   2          },
                 { "enum_pointer::pointer_mode_zero", 0          },
                 { "enum_pointer::pointer_mode_high", 2147483647 }
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
            targets = {
                { pointer_negative,                      pointer_maximum,                       static_cast<PointerState>(-19 - pass) },
                { PointerPhase::pointer_alias,           PointerPhase::pointer_idle,            static_cast<PointerPhase>(42 + pass)  },
                { enum_pointer::Mode::pointer_mode_high, enum_pointer::Mode::pointer_mode_zero,
                 static_cast<enum_pointer::Mode>(23 + pass)                                                                           }
            };
            model = {
                101 + pass,
                pass ? nullptr : &targets.states[1],
                pass ? nullptr : &targets.phases[2],
                pass ? nullptr : &targets.modes[2],
                pass ? &model.local : &targets.states[1],
                { &targets.states[0], nullptr, pass ? &model.local : &targets.states[1] },
                { { &targets.phases[0], &targets.phases[2] }, { nullptr, &targets.phases[2] } },
                pointer_negative,
                201 + pass
            };
            const auto expected_model   = model;
            const auto expected_targets = targets;
            std::ostringstream checkpoint;
            mm.write_checkpoint(checkpoint);
            std::ofstream("checkpoint-" + std::to_string(pass) + ".txt") << checkpoint.str();
            const auto text = checkpoint.str();
            probe::require(text.find("pointer_negative") != std::string::npos
                               && text.find("pointer_running") != std::string::npos
                               && text.find("enum_pointer::pointer_mode_high") != std::string::npos
                               && text.find("pointer_alias") == std::string::npos,
                           "symbolic enum checkpoint differs");
            model = {
                -1,
                &targets.states[0],
                &targets.phases[0],
                &targets.modes[0],
                nullptr,
                { nullptr, &model.local, nullptr },
                { { nullptr, nullptr }, { &targets.phases[0], nullptr } },
                static_cast<PointerState>(1),
                -1
            };
            for (auto& value : targets.states)
                value = static_cast<PointerState>(1);
            for (auto& value : targets.phases)
                value = static_cast<PointerPhase>(1);
            for (auto& value : targets.modes)
                value = static_cast<enum_pointer::Mode>(1);
            probe::require(!same(model, expected_model) && !same(targets, expected_targets),
                           "enum pointer control did not mutate storage");
            const int restored = mm.read_checkpoint_from_string(checkpoint.str().c_str());
            probe::require(restored == 0, "enum pointer checkpoint restore failed");
            probe::require(same(model, expected_model) && same(targets, expected_targets),
                           "enum pointer checkpoint values did not round trip");
            if (pass)
                std::cout << ',';
            std::cout << '[';
            bool first = true;
            auto item  = [&](const auto& value)
            {
                if (!first)
                    std::cout << ',';
                first = false;
                print(value, model, targets);
            };
            std::apply([&](const auto&... field) { (item(field), ...); }, members(model));
            std::apply([&](const auto&... field) { (item(field), ...); }, members(targets));
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
