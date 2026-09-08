// Execute the captured wrappers with the ownership split used by delete_var:
// calloc storage -> generated destruct -> free; scalar new -> generated delete.
#include "legacy.cpp"
#include "native_probe.hh"

#include <cstdint>
#include <dlfcn.h>
#include <new>
#include <utility>

namespace lifecycle_probe
{
    struct Event
    {
            int kind;
            int value;
            std::uintptr_t address;
    };
    Event events[32] { };
    size_t eventCount = 0;

    template <typename T, typename = void> struct PlacementDefault : std::false_type
    {
    };
    template <typename T>
    struct PlacementDefault<T, std::void_t<decltype(::new (static_cast<void*>(nullptr)) T())>> : std::true_type
    {
    };

    template <typename F> F symbol(const char* prefix, const char* name)
    {
        return reinterpret_cast<F>(dlsym(RTLD_DEFAULT, (std::string(prefix) + name).c_str()));
    }

    struct Wrappers
    {
            void* (*allocate)(int);
            void (*destruct)(void*, int);
            void (*deleteScalar)(void*);
    };

    Wrappers wrappers(const char* name)
    {
        return { symbol<void* (*)(int)>("io_src_allocate_", name),
                 symbol<void (*)(void*, int)>("io_src_destruct_", name),
                 symbol<void (*)(void*)>("io_src_delete_", name) };
    }

    template <typename T> void describe(const char* name)
    {
        auto functions = wrappers(name);
        std::cout << "{\"name\":";
        probe::quoted(name);
        std::cout << ",\"size_bytes\":" << sizeof(T) << ",\"pod\":" << std::is_pod<T>::value
                  << ",\"abstract\":" << std::is_abstract<T>::value
                  << ",\"default_placement\":" << PlacementDefault<T>::value
                  << ",\"default_constructible\":" << std::is_default_constructible<T>::value
                  << ",\"destructible\":" << std::is_destructible<T>::value
                  << ",\"virtual_destructor\":" << std::has_virtual_destructor<T>::value
                  << ",\"symbols\":{\"allocate\":" << (functions.allocate != nullptr)
                  << ",\"destruct\":" << (functions.destruct != nullptr)
                  << ",\"delete\":" << (functions.deleteScalar != nullptr) << "}}";
    }

    void emit(const char* name, const char* operation, std::uintptr_t base, int count, const std::vector<int>& initial,
              bool zeroed = false)
    {
        std::cout << "{\"name\":";
        probe::quoted(name);
        std::cout << ",\"operation\":";
        probe::quoted(operation);
        std::cout << ",\"count\":" << count << ",\"zeroed\":" << zeroed << ",\"initial\":[";
        for (size_t i = 0; i < initial.size(); ++i)
        {
            if (i)
                std::cout << ',';
            std::cout << initial[i];
        }
        std::cout << "],\"events\":[";
        for (size_t i = 0; i < eventCount; ++i)
        {
            if (i)
                std::cout << ',';
            probe::require(events[i].address >= base, "event address precedes allocation");
            std::cout << "{\"kind\":" << events[i].kind << ",\"value\":" << events[i].value
                      << ",\"offset_bytes\":" << events[i].address - base << '}';
            // Do not retain pointer-shaped integers that could hide a leak
            // from LeakSanitizer's conservative reachability scan.
            events[i] = { };
        }
        eventCount = 0;
        std::cout << "]}";
    }

    template <typename T> void allocated(const char* name, int count)
    {
        auto functions = wrappers(name);
        probe::require(functions.allocate && functions.destruct, "missing owning-allocation wrappers");
        auto* objects = static_cast<T*>(functions.allocate(count));
        probe::require(objects != nullptr, "legacy allocation failed");
        const auto address = reinterpret_cast<std::uintptr_t>(objects);
        std::vector<int> initial;
        for (int i = 0; i < count; ++i)
        {
            initial.push_back(objects[i].value);
            objects[i].value = 101 + i;
        }
        functions.destruct(objects, count);
        std::free(objects);
        emit(name, "allocate_destruct_free", address, count, initial);
    }

    void rawStorage(int count)
    {
        const char* name = "IcgLifecycleDeleted";
        auto functions   = wrappers(name);
        probe::require(functions.allocate && functions.destruct && functions.deleteScalar, "missing POD wrappers");
        void* storage = functions.allocate(count);
        probe::require(storage != nullptr, "raw allocation failed");
        const auto address = reinterpret_cast<std::uintptr_t>(storage);
        const size_t bytes = sizeof(IcgLifecycleDeleted) * count;
        bool zeroed        = true;
        for (size_t i = 0; i < bytes; ++i)
            zeroed = zeroed && static_cast<unsigned char*>(storage)[i] == 0;
        // No typed access or attempted construction of the deleted-default type.
        functions.destruct(storage, count);
        functions.deleteScalar(storage); // Captured POD delete is a no-op.
        // Both POD wrappers must leave storage owned by the caller.
        std::memset(storage, 0x5a, bytes);
        std::free(storage);
        emit(name, "raw_storage_noops_free", address, count, { }, zeroed);
    }

    void explicitConstruction(int count)
    {
        const char* name = "IcgLifecycleNoDefault";
        auto functions   = wrappers(name);
        probe::require(!functions.allocate && functions.destruct, "unexpected explicit-construction wrappers");
        void* storage = std::calloc(count, sizeof(IcgLifecycleNoDefault));
        probe::require(storage != nullptr, "probe allocation failed");
        const auto address = reinterpret_cast<std::uintptr_t>(storage);
        std::vector<int> initial;
        for (int i = 0; i < count; ++i)
        {
            auto* slot   = static_cast<unsigned char*>(storage) + i * sizeof(IcgLifecycleNoDefault);
            auto* object = ::new (slot) IcgLifecycleNoDefault(61 + i);
            initial.push_back(object->value);
            object->value = 101 + i;
        }
        functions.destruct(storage, count);
        std::free(storage);
        emit(name, "explicit_construct_destruct_free", address, count, initial);
    }

    template <typename T, typename... Args> void scalar(const char* name, Args... args)
    {
        auto functions = wrappers(name);
        probe::require(functions.deleteScalar != nullptr, "missing scalar-delete wrapper");
        T* object          = new T(args...);
        const auto address = reinterpret_cast<std::uintptr_t>(object);
        std::vector<int> initial { object->value };
        object->value = 201;
        functions.deleteScalar(object);
        emit(name, "new_scalar_delete", address, 1, initial);
    }

    class Concrete : public IcgLifecycleAbstract
    {
        public:
            void act() override { }
            ~Concrete() override;
    };

    void virtualDeletion()
    {
        const char* name = "IcgLifecycleAbstract";
        auto functions   = wrappers(name);
        probe::require(!functions.allocate && functions.deleteScalar, "unexpected abstract wrappers");
        IcgLifecycleAbstract* object = new Concrete;
        const auto address           = reinterpret_cast<std::uintptr_t>(object);
        functions.deleteScalar(object);
        emit(name, "derived_new_base_delete", address, 1, { });
    }
} // namespace lifecycle_probe

void icg_lifecycle_event(int kind, int value, const void* address)
{
    using namespace lifecycle_probe;
    probe::require(eventCount < 32, "unexpected lifecycle event count");
    events[eventCount++] = { kind, value, reinterpret_cast<std::uintptr_t>(address) };
}

lifecycle_probe::Concrete::~Concrete() { icg_lifecycle_event(3, 0, this); }

int main()
{
    using namespace lifecycle_probe;
    try
    {
        std::cout << std::boolalpha << "{\"records\":[";
        describe<IcgLifecycleTracked>("IcgLifecycleTracked");
        std::cout << ',';
        describe<IcgLifecycleImplicit>("IcgLifecycleImplicit");
        std::cout << ',';
        describe<IcgLifecycleDeleted>("IcgLifecycleDeleted");
        std::cout << ',';
        describe<IcgLifecycleNoDefault>("IcgLifecycleNoDefault");
        std::cout << ',';
        describe<IcgLifecyclePrivateDestructor>("IcgLifecyclePrivateDestructor");
        std::cout << ',';
        describe<IcgLifecycleAbstract>("IcgLifecycleAbstract");
        std::cout << "],\"executions\":[";
        for (int count : { 1, 3 })
        {
            if (count != 1)
                std::cout << ',';
            allocated<IcgLifecycleTracked>("IcgLifecycleTracked", count);
            std::cout << ',';
            allocated<IcgLifecycleImplicit>("IcgLifecycleImplicit", count);
            std::cout << ',';
            rawStorage(count);
            std::cout << ',';
            explicitConstruction(count);
        }
        std::cout << ',';
        scalar<IcgLifecycleTracked>("IcgLifecycleTracked");
        std::cout << ',';
        scalar<IcgLifecycleImplicit>("IcgLifecycleImplicit");
        std::cout << ',';
        scalar<IcgLifecycleNoDefault>("IcgLifecycleNoDefault", 61);
        std::cout << ',';
        virtualDeletion();
        std::cout << "]}\n";
        return 0;
    }
    catch (const std::exception& error)
    {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
