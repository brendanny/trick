#include "Lifecycle.hh"

// Implemented by the probe. Event kind 1 is construction, 2 is destruction.
void icg_lifecycle_event(int kind, int value, const void* address);

IcgLifecycleTracked::IcgLifecycleTracked()
    : value(41)
{
    icg_lifecycle_event(1, value, this);
}

IcgLifecycleTracked::~IcgLifecycleTracked() { icg_lifecycle_event(2, value, this); }

IcgLifecycleImplicit::~IcgLifecycleImplicit() { icg_lifecycle_event(2, value, this); }

IcgLifecycleNoDefault::IcgLifecycleNoDefault(int initial)
    : value(initial)
{
    icg_lifecycle_event(1, value, this);
}

IcgLifecycleNoDefault::~IcgLifecycleNoDefault() { icg_lifecycle_event(2, value, this); }

IcgLifecyclePrivateDestructor::IcgLifecyclePrivateDestructor() { icg_lifecycle_event(1, 0, this); }

IcgLifecyclePrivateDestructor::~IcgLifecyclePrivateDestructor() { icg_lifecycle_event(2, 0, this); }

IcgLifecycleAbstract::~IcgLifecycleAbstract() { icg_lifecycle_event(2, 0, this); }
