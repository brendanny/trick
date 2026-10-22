#include "trick/vs/Interfaces.hh"

namespace Trick
{
    namespace vs
    {

        // Out-of-line destructors, so each interface's vtable lives in this library.
        ResolvedVar::~ResolvedVar()         = default;
        Resolver::~Resolver()               = default;
        Clock::~Clock()                     = default;
        Conversion::~Conversion()           = default;
        UnitConverter::~UnitConverter()     = default;
        CommandFallback::~CommandFallback() = default;

    } // namespace vs
} // namespace Trick
