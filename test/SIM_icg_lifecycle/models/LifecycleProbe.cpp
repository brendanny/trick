#include "LifecycleProbe.hh"

#include "trick/MemoryManager.hh"

#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iterator>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace
{
    struct Event
    {
            int kind;
            int value;
            std::uintptr_t address;
            bool registered;
    };
    std::vector<Event> events;
    std::ostringstream executions;
    std::ostringstream rejections;
    std::ptrdiff_t initialAllocations = 0;
    int scenarioCount                 = 0;
    bool active                       = false;

    void require(bool condition, const char* message)
    {
        if (!condition)
            throw std::runtime_error(message);
    }

    std::ptrdiff_t allocations()
    {
        return std::distance(trick_MM->alloc_info_map_begin(), trick_MM->alloc_info_map_end());
    }

    void integers(const std::vector<int>& values)
    {
        executions << '[';
        for (size_t i = 0; i < values.size(); ++i)
        {
            if (i)
                executions << ',';
            executions << values[i];
        }
        executions << ']';
    }

    void start(const char* type, const char* operation, void* address, const char* name)
    {
        auto* info = trick_MM->get_alloc_info_at(address);
        require(info && info->name && info->user_type_name, "missing named lifecycle allocation");
        require(std::strcmp(info->name, name) == 0, "wrong allocation name");
        require(info->start == address && info->attr, "missing allocation metadata");
        require(info->num > 0 && info->size > 0, "invalid allocation size");
        const auto end  = reinterpret_cast<std::uintptr_t>(info->end);
        const auto base = reinterpret_cast<std::uintptr_t>(address);
        require(end >= base, "invalid allocation range");
        if (scenarioCount++)
            executions << ',';
        executions << "{\"type\":" << std::quoted(type) << ",\"operation\":" << std::quoted(operation)
                   << ",\"allocation\":{\"type\":" << std::quoted(info->user_type_name)
                   << ",\"size_bytes\":" << info->size << ",\"range_bytes\":" << end - base + 1
                   << ",\"count\":" << info->num
                   << ",\"storage\":" << std::quoted(info->stcl == TRICK_LOCAL ? "local" : "external")
                   << ",\"allocator\":"
                   << std::quoted(info->alloc_type == TRICK_ALLOC_MALLOC    ? "malloc"
                                      : info->alloc_type == TRICK_ALLOC_NEW ? "new"
                                                                            : "other")
                   << ",\"cpp\":" << (info->language == Language_CPP)
                   << ",\"structured\":" << (info->type == TRICK_STRUCTURED)
                   << ",\"named\":" << (trick_MM->var_exists(name) == 1)
                   << ",\"interior_lookup\":" << (trick_MM->get_alloc_info_of(info->end) == info) << ",\"dimensions\":";
        integers(std::vector<int>(info->index, info->index + info->num_index));
        executions << '}';
    }

    void finishScenario(void* address, const char* name, int status, const std::vector<int>& initial,
                        bool zeroed = false, int eventsAfterUnregister = -1)
    {
        const auto base = reinterpret_cast<std::uintptr_t>(address);
        executions << ",\"delete_status\":" << status
                   << ",\"unregistered\":" << (trick_MM->get_alloc_info_at(address) == nullptr)
                   << ",\"name_removed\":" << (trick_MM->var_exists(name) == 0) << ",\"zeroed\":" << zeroed
                   << ",\"events_after_unregister\":" << eventsAfterUnregister << ",\"initial\":";
        integers(initial);
        executions << ",\"events\":[";
        for (size_t i = 0; i < events.size(); ++i)
        {
            if (i)
                executions << ',';
            require(events[i].address >= base, "event before allocation");
            executions << "{\"kind\":" << events[i].kind << ",\"value\":" << events[i].value
                       << ",\"offset_bytes\":" << events[i].address - base << ",\"registered\":" << events[i].registered
                       << '}';
        }
        executions << "]}";
        events.clear();
    }

    template <typename T> void allocated(const char* type, int count)
    {
        const char* name = "icg_mm_allocated";
        int dimension    = count;
        auto* objects
            = static_cast<T*>(trick_MM->declare_var(TRICK_STRUCTURED, type, 0, name, count == 1 ? 0 : 1, &dimension));
        require(objects != nullptr, "MemoryManager allocation failed");
        start(type, count == 1 ? "declare_delete_name" : "declare_delete_address", objects, name);
        std::vector<int> initial;
        for (int i = 0; i < count; ++i)
        {
            initial.push_back(objects[i].value);
            objects[i].value = 101 + i;
        }
        const int status = count == 1 ? trick_MM->delete_var(std::string(name)) : trick_MM->delete_var(objects);
        finishScenario(objects, name, status, initial);
    }

    void rawStorage(int count)
    {
        const char* name              = "icg_mm_raw";
        const std::string declaration = "IcgLifecycleDeleted " + std::string(name) + (count == 1 ? "" : "[3]");
        void* storage                 = trick_MM->declare_var(declaration.c_str());
        require(storage != nullptr, "MemoryManager POD storage allocation failed");
        start("IcgLifecycleDeleted", count == 1 ? "raw_delete_name" : "raw_delete_address", storage, name);
        bool zeroed = true;
        for (size_t i = 0; i < sizeof(IcgLifecycleDeleted) * count; ++i)
            zeroed = zeroed && static_cast<unsigned char*>(storage)[i] == 0;
        // The default constructor is deleted: never perform typed object access.
        const int status = count == 1 ? trick_MM->delete_var(std::string(name)) : trick_MM->delete_var(storage);
        finishScenario(storage, name, status, { }, zeroed);
    }

    void external()
    {
        const char* name = "icg_mm_external";
        // Manual caller construction/destruction around unregistering external
        // storage lets us observe exactly when destruction occurs.
        alignas(IcgLifecycleTracked) unsigned char storage[sizeof(IcgLifecycleTracked)];
        auto* object = ::new (storage) IcgLifecycleTracked;
        require(trick_MM->declare_extern_var(object, "IcgLifecycleTracked icg_mm_external") == object,
                "external registration failed");
        start("IcgLifecycleTracked", "external_unregister", object, name);
        const int status = trick_MM->delete_extern_var(std::string(name));
        const int after  = static_cast<int>(events.size());
        // Unregistration must leave the caller's object alive and writable.
        object->value   = 301;
        const int value = object->value;
        object->~IcgLifecycleTracked();
        finishScenario(storage, name, status, { value }, false, after);
    }

    void rejected(const char* type, bool comma)
    {
        const auto before = allocations();
        // Anonymous failed requests avoid the legacy named-request failure
        // path's unrelated allocation-name leak.
        void* result = trick_MM->declare_var(type);
        if (comma)
            rejections << ',';
        rejections << "{\"type\":" << std::quoted(type) << ",\"null\":" << (result == nullptr)
                   << ",\"allocation_delta\":" << allocations() - before << ",\"events\":" << events.size() << '}';
        require(result == nullptr, "unsupported allocation unexpectedly succeeded");
    }

    template <typename T> void owned(T* object, const char* type, const char* name)
    {
        require(active && object, "named SWIG object is missing");
        start(type, "swig_named_delete", object, name);
        auto* info = trick_MM->get_alloc_info_at(object);
        // Do not change ownership flags in this probe. Observe the flags set
        // by the production SWIG TMMName constructor before calling delete_var.
        require(info->stcl == TRICK_LOCAL && info->alloc_type == TRICK_ALLOC_NEW,
                "SWIG did not transfer scalar-new ownership");
        const int initial = object->value;
        object->value     = 201;
        const int status  = trick_MM->delete_var(std::string(name));
        finishScenario(object, name, status, { initial });
    }
}

void icg_lifecycle_event(int kind, int value, const void* address)
{
    if (active)
    {
        require(events.size() < 32, "unexpected lifecycle event count");
        events.push_back({ kind, value, reinterpret_cast<std::uintptr_t>(address),
                           trick_MM->get_alloc_info_of(const_cast<void*>(address)) != nullptr });
    }
}

void LifecycleProbe::begin()
{
    require(!active && trick_MM, "lifecycle probe already running or MemoryManager missing");
    active = true;
    events.clear();
    executions.str("");
    rejections.str("");
    executions << std::boolalpha;
    rejections << std::boolalpha;
    scenarioCount      = 0;
    initialAllocations = allocations();
    for (int count : { 1, 3 })
    {
        allocated<IcgLifecycleTracked>("IcgLifecycleTracked", count);
        allocated<IcgLifecycleImplicit>("IcgLifecycleImplicit", count);
        rawStorage(count);
    }
    external();
    rejected("IcgLifecycleNoDefault", false);
    rejected("IcgLifecycleAbstract", true);
}

void LifecycleProbe::owned_tracked(IcgLifecycleTracked* object)
{
    owned(object, "IcgLifecycleTracked", "icg_mm_new_tracked");
}

void LifecycleProbe::owned_no_default(IcgLifecycleNoDefault* object)
{
    owned(object, "IcgLifecycleNoDefault", "icg_mm_new_explicit");
}

void LifecycleProbe::finish(const char* path)
{
    require(active && scenarioCount == 9 && events.empty(), "incomplete lifecycle execution");
    std::ofstream output(path);
    require(output.good(), "cannot open MemoryManager observation file");
    output << "{\"executions\":[" << executions.str() << "],\"rejections\":[" << rejections.str()
           << "],\"allocation_delta\":" << allocations() - initialAllocations << "}\n";
    output.close();
    require(!output.fail(), "cannot write MemoryManager observations");
    active = false;
}
