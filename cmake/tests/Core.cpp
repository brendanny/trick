#include "trick/Environment.hh"
#include "trick/MemoryManager.hh"

#include <cstring>

int main()
{
    Trick::MemoryManager memory;
    // The only reference to the generated allocator is a runtime lookup. This
    // fails if normal static archive elimination discards its metadata object.
    auto* environment = static_cast<Trick::Environment*>(memory.declare_var("Trick::Environment environment"));
    if (!environment)
    {
        return 1;
    }
    environment->add_var("TRICK_CMAKE_CORE_SMOKE", "native");
    const char* value = environment->get_var("TRICK_CMAKE_CORE_SMOKE");
    if (!value || std::strcmp(value, "native") != 0)
    {
        return 2;
    }
    return memory.delete_var(environment);
}
