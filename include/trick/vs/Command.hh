/*
PURPOSE: (Typed variable server commands.)

The parser (Phase 2) turns one line from a client into a Command. Each
session command that a client can send today has a type here. Any other
line becomes Fallback and runs in the Python input processor, as all lines
do today.
*/

#ifndef TRICK_VS_COMMAND_HH
#define TRICK_VS_COMMAND_HH

#include <cstdint>
#include <optional>
#include <string>
#include <variant>

namespace Trick
{
    namespace vs
    {
        namespace cmd
        {

            // Variable list
            struct VarAdd
            {
                    std::string name;
                    std::optional<std::string> units;
            };

            struct VarRemove
            {
                    std::string name;
            };

            struct VarUnits
            {
                    std::string name;
                    std::string units;
            };

            struct VarClear
            {
            };

            // Sending
            struct VarSend
            {
            };

            /** var_send_once("a,b,c"[, count]). The parser keeps the raw list; the
             *  session splits it as the old server does (on ',', no trimming). */
            struct VarSendOnce
            {
                    std::string names;
                    std::optional<int> count;
            };

            struct VarExists
            {
                    std::string name;
            };

            struct VarGetStlSize
            {
                    std::string name;
            };

            struct VarSendListSize
            {
            };

            // Timing and modes
            struct VarCycle
            {
                    double seconds = 0.0;
            };

            struct VarPause
            {
            };

            struct VarUnpause
            {
            };

            struct VarSetCopyMode
            {
                    int mode = 0;
            };

            struct VarSetWriteMode
            {
                    int mode = 0;
            };

            struct VarSync
            {
                    int mode = 0;
            };

            struct VarSetFrameMultiple
            {
                    uint32_t multiple = 1; ///< after the C conversion to unsigned int
            };

            struct VarSetFrameOffset
            {
                    uint32_t offset = 0; ///< after the C conversion to unsigned int
            };

            struct VarSetFreezeFrameMultiple
            {
                    uint32_t multiple = 1; ///< after the C conversion to unsigned int
            };

            struct VarSetFreezeFrameOffset
            {
                    uint32_t offset = 0; ///< after the C conversion to unsigned int
            };

            // Format
            struct VarAscii
            {
            };

            struct VarBinary
            {
            };

            struct VarBinaryNoNames
            {
            };

            struct VarByteswap
            {
                    bool on = false;
            };

            // Session settings
            struct VarValidateAddress
            {
                    bool on = false;
            };

            struct VarDebug
            {
                    int level = 0;
            };

            struct VarSetClientTag
            {
                    std::string tag;
            };

            struct VarSetSendStdio
            {
                    bool on = false;
            };

            struct VarWriteStdio
            {
                    int stream = 1;
                    std::string text;
            };

            struct VarServerLog
            {
                    bool on = false;
            };

            struct VarExit
            {
            };

            // Files
            struct SendSieResource
            {
            };

            struct SendSieClass
            {
            };

            struct SendSieEnum
            {
            };

            struct SendSieTopLevelObjects
            {
            };

            struct SendFile
            {
                    std::string path;
            };

            // Writes
            struct NoneValue
            {
            };

            inline bool operator==(NoneValue, NoneValue) noexcept { return true; }

            inline bool operator!=(NoneValue, NoneValue) noexcept { return false; }

            /** The value of var_set: a float, an integer, a string or None. */
            using SetValue = std::variant<double, long long, std::string, NoneValue>;

            struct VarSet
            {
                    std::string name;
                    SetValue value;
                    std::optional<std::string> units;
            };

            /** A line that is not a typed command. It runs in the Python input processor. */
            struct Fallback
            {
                    std::string text;
            };

        } // namespace cmd

        using Command
            = std::variant<cmd::VarAdd, cmd::VarRemove, cmd::VarUnits, cmd::VarClear, cmd::VarSend, cmd::VarSendOnce,
                           cmd::VarExists, cmd::VarGetStlSize, cmd::VarSendListSize, cmd::VarCycle, cmd::VarPause,
                           cmd::VarUnpause, cmd::VarSetCopyMode, cmd::VarSetWriteMode, cmd::VarSync,
                           cmd::VarSetFrameMultiple, cmd::VarSetFrameOffset, cmd::VarSetFreezeFrameMultiple,
                           cmd::VarSetFreezeFrameOffset, cmd::VarAscii, cmd::VarBinary, cmd::VarBinaryNoNames,
                           cmd::VarByteswap, cmd::VarValidateAddress, cmd::VarDebug, cmd::VarSetClientTag,
                           cmd::VarSetSendStdio, cmd::VarWriteStdio, cmd::VarServerLog, cmd::VarExit,
                           cmd::SendSieResource, cmd::SendSieClass, cmd::SendSieEnum,
                           cmd::SendSieTopLevelObjects, cmd::SendFile, cmd::VarSet, cmd::Fallback>;

        /**
         * The Python function name of a command, for example "var_add", as a client
         * writes it after "trick.". Fallback returns "".
         */
        const char* command_name(const Command& command) noexcept;

        /** True for Fallback. */
        inline bool is_fallback(const Command& command) noexcept
        {
            return std::holds_alternative<cmd::Fallback>(command);
        }

    } // namespace vs
} // namespace Trick

#endif
