#pragma once

namespace model
{
    /// Wire state, with a signed underlying representation.
    enum class State : signed char
    {
        /// No state has been assigned.
        Unknown = -1,
        Ready   = 0,
        Running = 3,
        Active  = Running
    };
    enum class Opaque : unsigned short;
    typedef enum
    {
        Cold,
        Warm = 7
    } Temperature;
    enum Limits : unsigned long long
    {
        Largest = 18446744073709551615ULL
    };
    using StateAlias = State;

    struct Packet
    {
            enum class Kind : unsigned
            {
                Data,
                Control
            };
            StateAlias state;
            Kind kind : 2;
            unsigned : 3;
            unsigned : 0;
            /// Payload length in units of words.
            unsigned count : 5;
            signed int delta : 7;
            bool valid : 1;
            Opaque future;
    };
}
