#include "trick2/registry.hpp"

#include <array>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace
{
    void check(bool condition, const char* message)
    {
        if (!condition)
            throw std::runtime_error(message);
    }
    template <class Exception, class F> void rejects(F&& action)
    {
        bool caught = false;
        try
        {
            action();
        }
        catch (const Exception&)
        {
            caught = true;
        }
        check(caught, "expected rejection did not occur");
    }

    struct Model
    {
            double position                = 1.0;
            const double reference         = 2.0;
            double command                 = 3.0;
            double saved                   = 4.0;
            int unsupported                = 0;
            volatile double volatile_value = 0.0;
    };
    using namespace trick2;
    constexpr auto fields
        = std::array { make_field<Model, &Model::position>({ 1, Unit::metre }, "position"),
                       make_field<Model, &Model::reference>({ 2, Unit::metre, Access::output }, "reference"),
                       make_field<Model, &Model::command>({ 3, Unit::dimensionless, Access::input }, "command"),
                       make_field<Model, &Model::saved>({ 4, Unit::dimensionless, Access::checkpoint }, "saved") };
    constexpr TypeDescriptor type { "Model", fields };
    template <auto Member>
    concept Describable = requires { make_field<Model, Member>({ 1 }, "field"); };
    static_assert(Describable<&Model::position> && Describable<&Model::reference>);
    static_assert(!Describable<&Model::unsupported> && !Describable<&Model::volatile_value>);

    void access_and_lifetime()
    {
        Registry registry;
        Model first, second;
        auto registration = registry.expose("vehicle", first, type);
        auto old_handle   = registration.handle();
        registry.write(old_handle, 1, 8.0);
        check(first.position == 8.0 && registry.read(old_handle, 1) == 8.0, "member write failed");
        check(registry.read(old_handle, 2) == 2.0, "const member read failed");
        rejects<std::logic_error>([&] { registry.write(old_handle, 2, 9.0); });
        rejects<std::logic_error>([&] { (void)registry.read(old_handle, 3); });
        rejects<std::logic_error>([&] { (void)registry.read(old_handle, 4); });
        rejects<std::out_of_range>([&] { (void)registry.read(old_handle, 99); });
        registry.write(old_handle, 3, 9.0);
        check(first.command == 9.0, "input-only field write failed");
        rejects<std::invalid_argument>([&] { (void)registry.expose("vehicle", second, type); });
        Registry other_registry;
        rejects<std::out_of_range>([&] { (void)other_registry.read(old_handle, 1); });

        auto snapshot = registry.snapshot();
        check(snapshot.size() == 1 && snapshot[0].fields.size() == 2, "snapshot exposed restricted fields");
        check(snapshot[0].fields[0].value == 8.0, "snapshot value wrong");
        Registration moved(std::move(registration));
        registration.reset();
        check(registry.read(moved.handle(), 1) == 8.0, "moved token lost registration");
        moved.reset();
        check(registry.snapshot().empty(), "reset left object registered");
        rejects<std::out_of_range>([&] { (void)registry.read(old_handle, 1); });
        auto replacement = registry.expose("vehicle", second, type);
        rejects<std::out_of_range>([&] { registry.write(old_handle, 1, 100.0); });
        check(registry.read(replacement.handle(), 1) == 1.0, "stale handle reached replacement");
        check(snapshot[0].name == "vehicle" && snapshot[0].fields[0].value == 8.0, "snapshot did not own its data");

        auto another = registry.expose("another", first, type);
        auto removed = another.handle();
        another      = std::move(replacement);
        rejects<std::out_of_range>([&] { (void)registry.read(removed, 1); });
        check(registry.read(another.handle(), 1) == 1.0, "move assignment lost new registration");
        registry.write(another.handle(), 1, std::numeric_limits<double>::infinity());
        check(std::isinf(second.position), "registry unexpectedly restricted doubles");
        registry.write(another.handle(), 1, std::numeric_limits<double>::quiet_NaN());
        check(std::isnan(registry.read(another.handle(), 1)), "NaN round trip failed");
    }

    void schema_validation_and_copying()
    {
        Registry registry;
        Model model;
        auto reject_schema = [&](auto modify)
        {
            auto invalid = fields;
            modify(invalid);
            rejects<std::invalid_argument>([&] { (void)registry.expose("vehicle", model, { "Model", invalid }); });
            check(registry.snapshot().empty(), "invalid schema mutated registry");
        };
        reject_schema([](auto& f) { f[0].id = 0; });
        reject_schema([](auto& f) { f[1].id = f[0].id; });
        reject_schema([](auto& f) { f[1].name = f[0].name; });
        reject_schema([](auto& f) { f[0].name = { }; });
        reject_schema([](auto& f) { f[0].read = nullptr; });
        reject_schema([](auto& f) { f[1].access = Access::input; });
        reject_schema([](auto& f) { f[0].unit = static_cast<Unit>(123); });
        reject_schema([](auto& f) { f[0].access = static_cast<Access>(128); });
        rejects<std::invalid_argument>([&] { (void)registry.expose("", model, type); });
        rejects<std::invalid_argument>([&] { (void)registry.expose("vehicle", model, { "", fields }); });

        Registration registration;
        {
            std::string object_name = "vehicle", type_name = "Model", field_name = "position";
            auto local_fields    = fields;
            local_fields[0].name = field_name;
            registration         = registry.expose(object_name, model, { type_name, local_fields });
            object_name          = "changed";
            type_name            = "changed";
            field_name           = "changed";
            local_fields[0].id   = 999;
        }
        auto snapshot = registry.snapshot();
        check(snapshot[0].name == "vehicle" && snapshot[0].type_name == "Model"
                  && snapshot[0].fields[0].name == "position",
              "registry borrowed schema storage");
        check(registry.read(registration.handle(), 1) == 1.0, "registry borrowed descriptor storage");
    }

    void destruction_order()
    {
        Model model;
        Registration survivor;
        ObjectHandle expired;
        {
            Registry registry;
            survivor = registry.expose("vehicle", model, type);
            expired  = survivor.handle();
        }
        Registry replacement;
        rejects<std::out_of_range>([&] { (void)replacement.read(expired, 1); });
        survivor.reset(); // Safe after the registry has been destroyed.
        {
            auto temporary = replacement.expose("vehicle", model, type);
            expired        = temporary.handle();
        }
        rejects<std::out_of_range>([&] { (void)replacement.read(expired, 1); });
    }
} // namespace

int main()
{
    try
    {
        access_and_lifetime();
        schema_validation_and_copying();
        destruction_order();
    }
    catch (const std::exception& error)
    {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
