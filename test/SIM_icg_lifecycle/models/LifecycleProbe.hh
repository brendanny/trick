/************************TRICK HEADER*************************
PURPOSE: (Observe production MemoryManager lifecycle behavior.)
LIBRARY DEPENDENCIES:
    ((LifecycleProbe.cpp)
     (../../../tools/icg_baseline/lifecycle/fixtures/Lifecycle.cpp))
*************************************************************/
#pragma once

#include "tools/icg_baseline/lifecycle/fixtures/Lifecycle.hh"

class LifecycleProbe
{
    public:
        void begin();
        void owned_tracked(IcgLifecycleTracked* object);
        void owned_no_default(IcgLifecycleNoDefault* object);
        void finish(const char* path);
};
