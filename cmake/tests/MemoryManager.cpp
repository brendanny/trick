#include "trick/MemoryManager.hh"

#include "trick/UdUnits.hh"
#include "trick/memorymanager_c_intf.h"
#include "trick/reference.h"

#include <sstream>

int main()
{
    Trick::UdUnits units;
    if (units.read_default_xml() != 0)
    {
        return 1;
    }
    Trick::MemoryManager memory;
    auto* values = static_cast<double*>(memory.declare_var("double values[3]"));
    if (!values)
    {
        return 2;
    }
    values[0]       = 12.0;
    REF2* reference = memory.ref_attributes("values[0]");
    if (!reference || reference->address != values)
    {
        return 3;
    }
    ref_free(reference);
    free(reference);
    std::istringstream checkpoint("values[1] = 42.5;\n");
    if (memory.read_checkpoint(&checkpoint) != 0 || values[1] != 42.5)
    {
        return 4;
    }
    if (memory.declare_var("double invalid[") != nullptr)
    {
        return 5;
    }
    return memory.delete_var(values);
}
