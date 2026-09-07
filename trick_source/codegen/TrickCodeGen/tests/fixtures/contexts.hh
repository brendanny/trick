#pragma once

/// Public model context.
namespace models
{
    inline namespace v1
    {
        typedef struct
        {
                int x;
                int y;
        } Point;
        struct Sample
        {
                Point position;
                union
                {
                        int count;
                        double weight;
                };
        };
    }
}

/// A second block shares the same namespace identity.
namespace models
{
    using Handle = Sample*;
}
namespace api     = models;
namespace current = api;

#define ICG_ANONYMOUS_RECORD                                                                                           \
    struct                                                                                                             \
    {                                                                                                                  \
            int value;                                                                                                 \
    }
#define ICG_TWO_RECORDS                                                                                                \
    ICG_ANONYMOUS_RECORD first;                                                                                        \
    ICG_ANONYMOUS_RECORD second;
namespace
{
    struct Local
    {
            ICG_TWO_RECORDS
    };
}
namespace
{
    using LocalHandle = Local*;
}
#undef ICG_TWO_RECORDS
#undef ICG_ANONYMOUS_RECORD
