#pragma once

namespace inheritance
{
    struct Empty
    {
    };
    struct Root
    {
            int value;
    };
    struct Other
    {
            double other;
    };
    using RootAlias = Root;
    struct Derived : RootAlias, Other
    {
            char tail;
    };
    struct EmptyDerived : Empty
    {
            int value;
    };

    struct Left : Root
    {
    };
    struct Right : Root
    {
    };
    struct Repeated : Left, Right
    {
    };

    struct VLeft : virtual Root
    {
            int left;
    };
    struct VRight : virtual Root
    {
            int right;
    };
    struct Diamond : VLeft, VRight
    {
            int own;
    };
    struct Bigger : Diamond
    {
            double extra[3];
    };
    struct Mixed : Left, VLeft
    {
            int own;
    };
    struct NestedVirtual : virtual VLeft
    {
            short inner;
    };

    class Private : Root
    {
    };
    struct Protected : protected Other
    {
    };
    struct __attribute__((packed)) PackedBase
    {
            short first;
            char second;
    };
    struct PackedChild : PackedBase
    {
            char third;
    };

    struct TailBase
    {
            int first;

        protected:
            char second;
    };
    struct TailDerived : TailBase
    {
            char third;
    };
}
