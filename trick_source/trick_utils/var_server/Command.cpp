#include "trick/vs/Command.hh"

namespace Trick
{
    namespace vs
    {

        namespace
        {

            // One overload per command type. A new alternative in Command without an
            // overload here does not compile.
            const char* name_of(const cmd::VarAdd&) noexcept { return "var_add"; }

            const char* name_of(const cmd::VarRemove&) noexcept { return "var_remove"; }

            const char* name_of(const cmd::VarUnits&) noexcept { return "var_units"; }

            const char* name_of(const cmd::VarClear&) noexcept { return "var_clear"; }

            const char* name_of(const cmd::VarSend&) noexcept { return "var_send"; }

            const char* name_of(const cmd::VarSendOnce&) noexcept { return "var_send_once"; }

            const char* name_of(const cmd::VarExists&) noexcept { return "var_exists"; }

            const char* name_of(const cmd::VarGetStlSize&) noexcept { return "var_get_stl_size"; }

            const char* name_of(const cmd::VarSendListSize&) noexcept { return "var_send_list_size"; }

            const char* name_of(const cmd::VarCycle&) noexcept { return "var_cycle"; }

            const char* name_of(const cmd::VarPause&) noexcept { return "var_pause"; }

            const char* name_of(const cmd::VarUnpause&) noexcept { return "var_unpause"; }

            const char* name_of(const cmd::VarSetCopyMode&) noexcept { return "var_set_copy_mode"; }

            const char* name_of(const cmd::VarSetWriteMode&) noexcept { return "var_set_write_mode"; }

            const char* name_of(const cmd::VarSync&) noexcept { return "var_sync"; }

            const char* name_of(const cmd::VarSetFrameMultiple&) noexcept { return "var_set_frame_multiple"; }

            const char* name_of(const cmd::VarSetFrameOffset&) noexcept { return "var_set_frame_offset"; }

            const char* name_of(const cmd::VarSetFreezeFrameMultiple&) noexcept
            {
                return "var_set_freeze_frame_multiple";
            }

            const char* name_of(const cmd::VarSetFreezeFrameOffset&) noexcept { return "var_set_freeze_frame_offset"; }

            const char* name_of(const cmd::VarAscii&) noexcept { return "var_ascii"; }

            const char* name_of(const cmd::VarBinary&) noexcept { return "var_binary"; }

            const char* name_of(const cmd::VarBinaryNoNames&) noexcept { return "var_binary_nonames"; }

            const char* name_of(const cmd::VarByteswap&) noexcept { return "var_byteswap"; }

            const char* name_of(const cmd::VarValidateAddress&) noexcept { return "var_validate_address"; }

            const char* name_of(const cmd::VarDebug&) noexcept { return "var_debug"; }

            const char* name_of(const cmd::VarSetClientTag&) noexcept { return "var_set_client_tag"; }

            const char* name_of(const cmd::VarSetSendStdio&) noexcept { return "var_set_send_stdio"; }

            const char* name_of(const cmd::VarWriteStdio&) noexcept { return "var_write_stdio"; }

            const char* name_of(const cmd::VarServerLog& c) noexcept
            {
                return c.on ? "var_server_log_on" : "var_server_log_off";
            }

            const char* name_of(const cmd::VarExit&) noexcept { return "var_exit"; }

            const char* name_of(const cmd::VarRetryBadRef&) noexcept { return "var_retry_bad_ref"; }

            const char* name_of(const cmd::SendSieResource&) noexcept { return "send_sie_resource"; }

            const char* name_of(const cmd::SendSieClass&) noexcept { return "send_sie_class"; }

            const char* name_of(const cmd::SendSieEnum&) noexcept { return "send_sie_enum"; }

            const char* name_of(const cmd::SendSieTopLevelObjects&) noexcept { return "send_sie_top_level_objects"; }

            const char* name_of(const cmd::SendFile&) noexcept { return "send_file"; }

            const char* name_of(const cmd::VarSet&) noexcept { return "var_set"; }

            const char* name_of(const cmd::Fallback&) noexcept { return ""; }

        } // namespace

        const char* command_name(const Command& command) noexcept
        {
            // std::visit can throw bad_variant_access only for a valueless variant,
            // which a Command never is: every alternative is nothrow-movable.
            return std::visit([](const auto& c) noexcept { return name_of(c); }, command);
        }

    } // namespace vs
} // namespace Trick
