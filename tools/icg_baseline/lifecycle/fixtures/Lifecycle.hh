// Focused Phase 0 lifecycle evidence. Definitions record events out of line so
// instrumentation headers do not become part of the extractor's input graph.
#pragma once

class IcgLifecycleTracked
{
    public:
        int value;
        IcgLifecycleTracked();
        ~IcgLifecycleTracked();
};

class IcgLifecycleImplicit
{
    public:
        int value = 17;
        ~IcgLifecycleImplicit();
};

class IcgLifecycleDeleted
{
    public:
        int value;
        IcgLifecycleDeleted() = delete;
};

class IcgLifecycleNoDefault
{
    public:
        int value;
        explicit IcgLifecycleNoDefault(int initial);
        ~IcgLifecycleNoDefault();
};

class IcgLifecyclePrivateDestructor
{
    public:
        IcgLifecyclePrivateDestructor();

    private:
        ~IcgLifecyclePrivateDestructor();
};

class IcgLifecycleAbstract
{
    public:
        virtual void act() = 0;
        virtual ~IcgLifecycleAbstract();
};
