#include "trick2/registry.hpp"

#include <algorithm>
#include <limits>
#include <optional>
#include <stdexcept>

namespace trick2
{
    namespace detail
    {
        struct OwnedField
        {
                std::uint32_t id;
                std::string name;
                Unit unit;
                Access access;
                double (*read)(const void*);
                void (*write)(void*, double);
        };
        struct ObjectRecord
        {
                std::string name;
                std::string type_name;
                void* address;
                std::vector<OwnedField> fields;
        };
        struct Slot
        {
                std::uint64_t generation = 1;
                std::optional<ObjectRecord> object;
        };
        struct RegistryState
        {
                std::vector<Slot> slots;
        };

        ObjectRecord& checked_object(RegistryState& state, std::size_t index, std::uint64_t generation)
        {
            if (index >= state.slots.size() || !state.slots[index].object
                || state.slots[index].generation != generation)
            {
                throw std::out_of_range("stale object handle");
            }
            return *state.slots[index].object;
        }
        const OwnedField& checked_field(const ObjectRecord& object, std::uint32_t id)
        {
            auto field = std::find_if(object.fields.begin(), object.fields.end(),
                                      [id](const auto& candidate) { return candidate.id == id; });
            if (field == object.fields.end())
                throw std::out_of_range("unknown field ID");
            return *field;
        }
    } // namespace detail

    Registration::~Registration() { reset(); }
    Registration::Registration(Registration&& other) noexcept
        : handle_(std::exchange(other.handle_, { }))
    {
    }
    Registration& Registration::operator=(Registration&& other) noexcept
    {
        if (this != &other)
        {
            reset();
            handle_ = std::exchange(other.handle_, { });
        }
        return *this;
    }
    void Registration::reset() noexcept
    {
        auto handle = std::exchange(handle_, { });
        if (auto state = handle.owner_.lock(); state && handle.slot_ < state->slots.size())
        {
            auto& slot = state->slots[handle.slot_];
            if (slot.object && slot.generation == handle.generation_)
            {
                slot.object.reset();
                // Retire the slot at saturation rather than ever revalidating a stale handle.
                if (slot.generation != std::numeric_limits<std::uint64_t>::max())
                    ++slot.generation;
            }
        }
    }

    Registry::Registry()
        : state_(std::make_shared<detail::RegistryState>())
    {
    }
    Registry::~Registry() = default;

    Registration Registry::expose_borrowed(std::string_view name, void* address, const TypeDescriptor& type)
    {
        if (name.empty() || type.name.empty())
            throw std::invalid_argument("object and type names must be nonempty");
        for (const auto& slot : state_->slots)
        {
            if (slot.object && slot.object->name == name)
                throw std::invalid_argument("duplicate object name");
        }
        detail::ObjectRecord object { std::string(name), std::string(type.name), address, { } };
        object.fields.reserve(type.fields.size());
        for (const auto& field : type.fields)
        {
            if (field.id == 0 || field.name.empty() || !valid_unit(field.unit) || !valid_access(field.access)
                || !field.read || (has_access(field.access, Access::input) && !field.write))
            {
                throw std::invalid_argument("invalid field descriptor");
            }
            for (const auto& previous : object.fields)
            {
                if (previous.id == field.id || previous.name == field.name)
                {
                    throw std::invalid_argument("duplicate field ID or name");
                }
            }
            object.fields.push_back(
                { field.id, std::string(field.name), field.unit, field.access, field.read, field.write });
        }
        for (std::size_t i = 0; i < state_->slots.size(); ++i)
        {
            auto& slot = state_->slots[i];
            if (!slot.object && slot.generation != std::numeric_limits<std::uint64_t>::max())
            {
                slot.object.emplace(std::move(object));
                return Registration(ObjectHandle(state_, i, slot.generation));
            }
        }
        state_->slots.push_back({ 1, std::move(object) });
        return Registration(ObjectHandle(state_, state_->slots.size() - 1, 1));
    }

    double Registry::read(const ObjectHandle& handle, std::uint32_t field_id) const
    {
        if (handle.owner_.lock() != state_)
            throw std::out_of_range("object handle belongs to another registry");
        const auto& object = detail::checked_object(*state_, handle.slot_, handle.generation_);
        const auto& field  = detail::checked_field(object, field_id);
        if (!has_access(field.access, Access::output))
            throw std::logic_error("field is not readable");
        return field.read(object.address);
    }

    void Registry::write(const ObjectHandle& handle, std::uint32_t field_id, double value)
    {
        if (handle.owner_.lock() != state_)
            throw std::out_of_range("object handle belongs to another registry");
        auto& object      = detail::checked_object(*state_, handle.slot_, handle.generation_);
        const auto& field = detail::checked_field(object, field_id);
        if (!has_access(field.access, Access::input))
            throw std::logic_error("field is not writable");
        field.write(object.address, value);
    }

    std::vector<ObjectSnapshot> Registry::snapshot() const
    {
        std::vector<ObjectSnapshot> result;
        for (const auto& slot : state_->slots)
        {
            if (!slot.object)
                continue;
            const auto& object = *slot.object;
            ObjectSnapshot copy { object.name, object.type_name, { } };
            for (const auto& field : object.fields)
            {
                if (has_access(field.access, Access::output))
                {
                    copy.fields.push_back({ field.id, field.name, field.unit, field.read(object.address) });
                }
            }
            result.push_back(std::move(copy));
        }
        return result;
    }

} // namespace trick2
