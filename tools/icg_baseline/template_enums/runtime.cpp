// Independent enum template storage and symbolic checkpoint observations.
#include "metadata.cpp"
#include "native_probe.hh"

#include "trick/MemoryManager.hh"

#include <clocale>
#include <fstream>
#include <sstream>

namespace
{
    template <class T> struct IsBox : std::false_type
    {
    };
    template <class T> struct IsBox<EnumBox<T>> : std::true_type
    {
    };
    template <class T> bool equal(const T& a, const T& b)
    {
        if constexpr (std::is_array<T>::value)
        {
            for (size_t i = 0; i < std::extent<T>::value; ++i)
                if (!equal(a[i], b[i]))
                    return false;
            return true;
        }
        else if constexpr (IsBox<T>::value)
            return equal(a.value, b.value) && equal(a.values, b.values) && equal(a.matrix, b.matrix);
        else
            return a == b;
    }
    template <class T> bool same(const EnumBox<T>& a, const EnumBox<T>& b)
    {
        return equal(a.value, b.value) && equal(a.values, b.values) && equal(a.matrix, b.matrix);
    }
    template <class T> void fill(T& field, const int (&values)[4], int& index)
    {
        if constexpr (std::is_array<T>::value)
        {
            for (auto& value : field)
                fill(value, values, index);
        }
        else if constexpr (IsBox<T>::value)
        {
            fill(field.value, values, index);
            fill(field.values, values, index);
            fill(field.matrix, values, index);
        }
        else
            field = static_cast<T>(values[index++ % 4]);
    }
    template <class T> void set(EnumBox<T>& box, const int (&values)[4], int pass)
    {
        int index = pass;
        fill(box.value, values, index);
        fill(box.values, values, index);
        fill(box.matrix, values, index);
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
        else if constexpr (IsBox<T>::value)
        {
            std::cout << '[';
            print(field.value);
            std::cout << ',';
            print(field.values);
            std::cout << ',';
            print(field.matrix);
            std::cout << ']';
        }
        else
            std::cout << static_cast<long long>(field);
    }
    template <class T> void print_box(const EnumBox<T>& box)
    {
        print(box.value);
        std::cout << ',';
        print(box.values);
        std::cout << ',';
        print(box.matrix);
    }
}

int main()
{
    try
    {
        probe::require(std::setlocale(LC_ALL, "C") != nullptr, "C locale unavailable");
        EnumBox<EnumState> state { };
        EnumBox<EnumPhase> phase { };
        EnumBox<enum_fixture::Mode> mode { };
        EnumBox<EnumPhase[2]> pairs { };
        EnumBox<EnumBox<EnumState>> nested { };
        Trick::MemoryManager mm;
        probe::require(mm.declare_extern_var(&nested, "EnumConsumers_nested_EnumBox_EnumBox_enum_EnumState___ nested")
                           == &nested,
                       "nested registration");
        probe::require(mm.declare_extern_var(&state, "EnumConsumers_plain_EnumBox_enum_EnumState_ state") == &state,
                       "state registration");
        probe::require(mm.declare_extern_var(&phase, "EnumConsumers_scoped_EnumBox_enum_EnumPhase_ phase") == &phase,
                       "phase registration");
        probe::require(mm.declare_extern_var(&mode, "EnumConsumers_namespaced_EnumBox_enum_enum_fixture__Mode_ mode")
                           == &mode,
                       "mode registration");
        probe::require(mm.declare_extern_var(&pairs, "EnumConsumers_array_argument_EnumBox_enum_EnumPhase_2__ pairs")
                           == &pairs,
                       "array argument registration");
        mm.set_reduced_checkpoint(false);
        mm.set_hexfloat_checkpoint(false);
        mm.set_hexfloat_decimal_comment_checkpoint(false);
        for (const auto& item : {
                 std::pair<const char*, int> { "state_negative",          -3         },
                 { "state_zero",              0          },
                 { "state_maximum",           2147483647 },
                 { "phase_idle",              0          },
                 { "phase_running",           2          },
                 { "phase_alias",             2          },
                 { "enum_fixture::mode_zero", 0          },
                 { "enum_fixture::mode_high", 2147483647 }
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
            // Include named values, duplicate-valued labels, and unnamed numeric values.
            set(state, { -3, 0, 2147483647, -19 }, pass);
            set(phase, { 0, 2, 42, -4 }, pass);
            set(mode, { 0, 2147483647, 19, 23 }, pass);
            set(pairs, { 0, 2, 42, -4 }, pass);
            set(nested, { -3, 0, 2147483647, -19 }, pass);
            const auto expected_nested = nested;
            const auto expected_state  = state;
            const auto expected_phase  = phase;
            const auto expected_mode   = mode;
            const auto expected_pairs  = pairs;
            std::ostringstream checkpoint;
            mm.write_checkpoint(checkpoint);
            std::ofstream(std::string("checkpoint-") + std::to_string(pass) + ".txt") << checkpoint.str();
            const auto text = checkpoint.str();
            probe::require(text.find("state_negative") != std::string::npos
                               && text.find("phase_running") != std::string::npos
                               && text.find("enum_fixture::mode_high") != std::string::npos
                               && text.find("phase_alias") == std::string::npos,
                           "symbolic enum checkpoint differs");
            set(state, { 1, 1, 1, 1 }, 0);
            set(phase, { 1, 1, 1, 1 }, 0);
            set(mode, { 1, 1, 1, 1 }, 0);
            set(pairs, { 1, 1, 1, 1 }, 0);
            set(nested, { 1, 1, 1, 1 }, 0);
            probe::require(!same(state, expected_state) && !same(phase, expected_phase) && !same(mode, expected_mode)
                               && !same(pairs, expected_pairs) && !same(nested, expected_nested),
                           "enum control did not mutate storage");
            const int restored = mm.read_checkpoint_from_string(checkpoint.str().c_str());
            probe::require(restored == 0, "enum checkpoint restore failed");
            probe::require(same(state, expected_state) && same(phase, expected_phase) && same(mode, expected_mode)
                               && same(pairs, expected_pairs) && same(nested, expected_nested),
                           "template enum checkpoint values did not round trip");
            if (pass)
                std::cout << ',';
            std::cout << '[';
            print_box(state);
            std::cout << ',';
            print_box(phase);
            std::cout << ',';
            print_box(mode);
            std::cout << ',';
            print_box(pairs);
            std::cout << ',';
            print_box(nested);
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
