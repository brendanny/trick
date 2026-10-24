#pragma once

#include <concepts>
#include <cstdint>
#include <span>
#include <string_view>
#include <type_traits>
#include <utility>

namespace trick2
{

    enum class Unit
    {
        dimensionless,
        metre,
        metre_per_second,
        radian_per_second
    };
    // Checkpoint is reserved metadata; it currently imposes no restore/writability rule.
    enum class Access : std::uint8_t
    {
        none       = 0,
        output     = 1,
        input      = 2,
        checkpoint = 4
    };

    constexpr Access operator|(Access left, Access right) noexcept
    {
        return static_cast<Access>(static_cast<unsigned>(left) | static_cast<unsigned>(right));
    }
    constexpr Access operator&(Access left, Access right) noexcept
    {
        return static_cast<Access>(static_cast<unsigned>(left) & static_cast<unsigned>(right));
    }
    constexpr bool has_access(Access value, Access flag) noexcept { return (value & flag) == flag; }
    constexpr bool valid_access(Access value) noexcept { return (static_cast<unsigned>(value) & ~7U) == 0; }
    constexpr bool valid_unit(Unit value) noexcept
    {
        switch (value)
        {
        case Unit::dimensionless:
        case Unit::metre:
        case Unit::metre_per_second:
        case Unit::radian_per_second:
            return true;
        }
        return false;
    }

    // A structural type usable as a C++26 reflection annotation.
    struct Field
    {
            std::uint32_t id;
            Unit unit     = Unit::dimensionless;
            Access access = Access::output | Access::input | Access::checkpoint;
    };

    struct FieldDescriptor
    {
            std::uint32_t id;
            std::string_view name;
            Unit unit;
            Access access;
            double (*read)(const void*);
            void (*write)(void*, double); // Null for const fields.
    };

    // Type erasure does not prove these callbacks match a registered object's type.
    // Every callback must have been instantiated for that object's concrete type.
    struct TypeDescriptor
    {
            std::string_view name;
            std::span<const FieldDescriptor> fields;
    };

    // The explicit descriptor path exercises the runtime without reflection support.
    // Values are accessed through their actual C++ members, never byte offsets.
    template <class T, auto Member>
        requires std::is_member_object_pointer_v<decltype(Member)> && requires(T& value) { value.*Member; }
    && (std::same_as<decltype(std::declval<T&>().*Member), double&>
        || std::same_as<decltype(std::declval<T&>().*Member), const double&>)
    constexpr FieldDescriptor make_field(Field policy, std::string_view name)
    {
        FieldDescriptor result { policy.id,
                                 name,
                                 policy.unit,
                                 policy.access,
                                 +[](const void* object) -> double { return static_cast<const T*>(object)->*Member; },
                                 nullptr };
        if constexpr (std::same_as<decltype(std::declval<T&>().*Member), double&>)
        {
            result.write = +[](void* object, double value)
            {
                static_cast<T*>(object)->*Member = value;
            };
        }
        return result;
    }

} // namespace trick2
