#pragma once

#include "trick2/schema.hpp"

#include <cstddef>
#include <memory>
#include <string>
#include <vector>

namespace trick2
{
    namespace detail
    {
        struct RegistryState;
    }

    class ObjectHandle
    {
        public:
            ObjectHandle() = default;

        private:
            friend class Registry;
            friend class Registration;
            ObjectHandle(const std::shared_ptr<detail::RegistryState>& owner, std::size_t slot,
                         std::uint64_t generation)
                : owner_(owner)
                , slot_(slot)
                , generation_(generation)
            {
            }
            std::weak_ptr<detail::RegistryState> owner_;
            std::size_t slot_         = 0;
            std::uint64_t generation_ = 0;
    };

    // The borrowed model must outlive its registration. This token never owns it.
    class Registration
    {
        public:
            Registration() = default;
            ~Registration();
            Registration(Registration&& other) noexcept;
            Registration& operator=(Registration&& other) noexcept;
            Registration(const Registration&)            = delete;
            Registration& operator=(const Registration&) = delete;
            ObjectHandle handle() const noexcept { return handle_; }
            void reset() noexcept;

        private:
            friend class Registry;
            explicit Registration(ObjectHandle handle)
                : handle_(std::move(handle))
            {
            }
            ObjectHandle handle_;
    };

    struct FieldSnapshot
    {
            std::uint32_t id;
            std::string name;
            Unit unit;
            double value;
    };
    struct ObjectSnapshot
    {
            std::string name;
            std::string type_name;
            std::vector<FieldSnapshot> fields;
    };

    // All operations, including token destruction, require external serialization.
    // Descriptors must describe the supplied object. Names and descriptors are copied;
    // the object itself must remain alive at the same address until token reset.
    // Callback code must remain loaded for that lifetime. No runtime type check is made.
    class Registry
    {
        public:
            Registry();
            ~Registry();
            Registry(const Registry&)            = delete;
            Registry& operator=(const Registry&) = delete;
            Registry(Registry&&)                 = delete;
            Registry& operator=(Registry&&)      = delete;

            template <class T>
                requires(!std::is_const_v<T> && !std::is_volatile_v<T>)
            [[nodiscard]] Registration expose(std::string_view name, T& object, const TypeDescriptor& type)
            {
                return expose_borrowed(name, std::addressof(object), type);
            }
            double read(const ObjectHandle& handle, std::uint32_t field_id) const;
            void write(const ObjectHandle& handle, std::uint32_t field_id, double value);
            // Copies output-permitted values. This is telemetry, not a checkpoint format.
            std::vector<ObjectSnapshot> snapshot() const;

        private:
            Registration expose_borrowed(std::string_view name, void* object, const TypeDescriptor& type);
            std::shared_ptr<detail::RegistryState> state_;
    };

} // namespace trick2
