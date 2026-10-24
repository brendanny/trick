#include <array>
#include <cstddef>
#include <meta>
#include <string_view>

struct FieldTag
{
        unsigned id;
};

struct Probe
{
        [[= FieldTag { 42 }]] double value { 1.0 };
};

template <class T, std::meta::info Member> double read_member(const void* object)
{
    return static_cast<const T*>(object)->[:Member:];
}

struct Descriptor
{
        unsigned id;
        std::string_view name;
        double (*read)(const void*);
};

consteval auto make_probe_schema()
{
    static constexpr auto members = std::define_static_array(
        std::meta::nonstatic_data_members_of(^^Probe, std::meta::access_context::unprivileged()));
    std::array<Descriptor, members.size()> descriptors { };
    std::size_t index = 0;
    template for (constexpr auto member : members)
    {
        constexpr auto annotations = std::define_static_array(std::meta::annotations_of_with_type(member, ^^FieldTag));
        static_assert(annotations.size() == 1);
        constexpr auto tag   = std::meta::extract<FieldTag>(annotations[0]);
        descriptors[index++] = { tag.id, std::meta::identifier_of(member), &read_member<Probe, member> };
    }
    return descriptors;
}

constexpr auto probe_schema = make_probe_schema();
static_assert(probe_schema.size() == 1);
static_assert(probe_schema[0].id == 42);
static_assert(probe_schema[0].name == "value");

int main()
{
    Probe object;
    return probe_schema[0].read(&object) == 1.0 ? 0 : 1;
}
