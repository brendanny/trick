#pragma once

#include "trick2/schema.hpp"

#include <array>
#include <concepts>
#include <cstddef>
#include <meta>
#include <type_traits>

namespace trick2
{
    namespace detail
    {

        template <class T, std::meta::info Member> double read_reflected_field(const void* object) noexcept
        {
            return static_cast<const T*>(object)->[:Member:];
        }

        template <class T, std::meta::info Member> void write_reflected_field(void* object, double value) noexcept
        {
            static_cast<T*>(object)->[:Member:] = value;
        }

        template <class T> consteval auto reflected_fields()
        {
            // Iterating expansion statements need a constant address for their range.
            static constexpr auto members = std::define_static_array(
                std::meta::nonstatic_data_members_of(^^T, std::meta::access_context::unprivileged()));
            std::array<FieldDescriptor, members.size()> result { };
            std::size_t index = 0;

            template for (constexpr auto member : members)
            {
                constexpr auto annotations
                    = std::define_static_array(std::meta::annotations_of_with_type(member, ^^Field));
                static_assert(annotations.size() == 1,
                              "each model field requires exactly one trick2::Field annotation");

                using Value = typename[:std::meta::type_of(member):];
                static_assert(std::same_as<std::remove_const_t<Value>, double>,
                              "reflected model fields must be double or const double");

                if constexpr (annotations.size() == 1 && std::same_as<std::remove_const_t<Value>, double>)
                {
                    constexpr auto policy = std::meta::extract<Field>(annotations[0]);
                    static_assert(policy.id != 0, "model field IDs must be nonzero");
                    static_assert(valid_unit(policy.unit), "invalid model field unit");
                    static_assert(valid_access(policy.access), "invalid model field access flags");
                    static_assert(!std::is_const_v<Value> || !has_access(policy.access, Access::input),
                                  "const model fields cannot have input access");

                    FieldDescriptor descriptor {
                        policy.id,     std::meta::identifier_of(member), policy.unit,
                        policy.access, &read_reflected_field<T, member>, nullptr,
                    };
                    if constexpr (!std::is_const_v<Value>)
                    {
                        descriptor.write = &write_reflected_field<T, member>;
                    }
                    result[index++] = descriptor;
                }
            }
            return result;
        }

        template <std::size_t N> constexpr bool unique_field_ids(const std::array<FieldDescriptor, N>& fields)
        {
            for (std::size_t i = 0; i < N; ++i)
            {
                for (std::size_t j = i + 1; j < N; ++j)
                {
                    if (fields[i].id == fields[j].id)
                    {
                        return false;
                    }
                }
            }
            return true;
        }

    } // namespace detail

    // The returned array contains ordinary runtime metadata and typed accessors.
    // Keep it alive for as long as a TypeDescriptor refers to its fields.
    // This first adapter describes complete, flat models with public scalar state.
    template <class T> consteval auto describe()
    {
        static_assert(std::is_class_v<T>, "describe requires a class or struct, not a union");
        static_assert(std::same_as<T, std::remove_cv_t<T>>, "describe requires an unqualified model type");
        static_assert(requires { sizeof(T); }, "describe requires the complete model definition");

        if constexpr (std::is_class_v<T> && requires { sizeof(T); })
        {
            constexpr auto context = std::meta::access_context::unprivileged();
            static_assert(std::meta::bases_of(^^T, context).empty() && !std::meta::has_inaccessible_bases(^^T, context),
                          "model base classes require an explicit adapter");
            static_assert(!std::meta::has_inaccessible_nonstatic_data_members(^^T, context),
                          "non-public model fields require an explicit adapter");

            constexpr auto fields = detail::reflected_fields<T>();
            static_assert(detail::unique_field_ids(fields), "model field IDs must be unique");
            return fields;
        }
        else
        {
            return std::array<FieldDescriptor, 0> { };
        }
    }

} // namespace trick2
