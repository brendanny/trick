/*
PURPOSE: (Numbers that appear on the variable server wire: type codes,
          message types, copy and write modes.)

The values are fixed by the protocol. They must not change.
*/

#ifndef TRICK_VS_WIRETYPES_HH
#define TRICK_VS_WIRETYPES_HH

#include <cstdint>

namespace Trick
{
    namespace vs
    {

        /**
         * The type code of a value in a binary reply. The numbers are the same as
         * TRICK_TYPE in trick/parameter_types.h; the adapter checks this with
         * static_assert. BadRef is TRICK_NUMBER_OF_TYPES, which the old server sends
         * for a name it cannot resolve (decision 1: keep 25).
         */
        enum class WireType : int32_t
        {
            Void              = 0,
            Character         = 1,
            UnsignedCharacter = 2,
            String            = 3,
            Short             = 4,
            UnsignedShort     = 5,
            Integer           = 6,
            UnsignedInteger   = 7,
            Long              = 8,
            UnsignedLong      = 9,
            Float             = 10,
            Double            = 11,
            Bitfield          = 12,
            UnsignedBitfield  = 13,
            LongLong          = 14,
            UnsignedLongLong  = 15,
            FilePtr           = 16,
            Boolean           = 17,
            WideCharacter     = 18,
            WideString        = 19,
            VoidPtr           = 20,
            Enumerated        = 21,
            Structured        = 22,
            Opaque            = 23,
            Stl               = 24,
            BadRef            = 25
        };

        /** The first int32 of every reply. */
        enum class MessageType : int32_t
        {
            IpError     = -1,
            VarList     = 0,
            VarExists   = 1,
            SieResource = 2,
            ListSize    = 3,
            Stdio       = 4,
            SendOnce    = 5,
            StlSize     = 6
        };

        /** Where and when a session copies values from simulation memory. */
        enum class CopyMode : int32_t
        {
            Async      = 0, ///< the session thread, every cycle
            Scheduled  = 1, ///< the main thread, at the end of the frame, every cycle
            TopOfFrame = 2  ///< the main thread, at the top of selected frames
        };

        /** Which thread sends a copied snapshot. */
        enum class WriteMode : int32_t
        {
            Async      = 0, ///< the session thread, every cycle
            WhenCopied = 1  ///< as soon as the main thread copies (real time only)
        };

        /** Reply encoding. */
        enum class Format
        {
            Ascii,
            Binary,
            BinaryNoNames
        };

        /** Name of a wire type, for logs and test output. */
        const char* wire_type_name(WireType type) noexcept;

        /** True if `code` is a WireType value. */
        bool is_wire_type(int32_t code) noexcept;

    } // namespace vs
} // namespace Trick

#endif
