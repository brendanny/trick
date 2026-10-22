#include "trick/vs/Command.hh"

#include <set>
#include <string>
#include <type_traits>

#include <gtest/gtest.h>

using namespace Trick::vs;

namespace
{

    // Build one default value of every alternative of Command.
    template <std::size_t... I> std::vector<Command> every_command(std::index_sequence<I...>)
    {
        return { Command(std::in_place_index<I>)... };
    }

    std::vector<Command> every_command()
    {
        return every_command(std::make_index_sequence<std::variant_size_v<Command>> { });
    }

} // namespace

TEST(Command, EveryTypedCommandHasAUniqueName)
{
    std::set<std::string> names;
    for (const Command& c : every_command())
    {
        const std::string name = command_name(c);
        if (is_fallback(c))
        {
            EXPECT_EQ(name, "");
            continue;
        }
        EXPECT_FALSE(name.empty());
        EXPECT_TRUE(names.insert(name).second) << "duplicate name " << name;
    }
    // Every alternative but Fallback has a name. (var_server_log_on and _off
    // share a type; a default VarServerLog names var_server_log_off.)
    EXPECT_EQ(names.size(), std::variant_size_v<Command> - 1);
}

// The names are what clients send after "trick.", so they must not change.
TEST(Command, NamesMatchThePythonApi)
{
    EXPECT_STREQ(command_name(cmd::VarAdd { "a.b", std::nullopt }), "var_add");
    EXPECT_STREQ(command_name(cmd::VarSendOnce { "a,b", 2 }), "var_send_once");
    EXPECT_STREQ(command_name(cmd::VarBinaryNoNames { }), "var_binary_nonames");
    EXPECT_STREQ(command_name(cmd::VarSetFreezeFrameOffset { }), "var_set_freeze_frame_offset");
    EXPECT_STREQ(command_name(cmd::SendSieTopLevelObjects { }), "send_sie_top_level_objects");
    EXPECT_STREQ(command_name(cmd::VarServerLog { true }), "var_server_log_on");
    EXPECT_STREQ(command_name(cmd::VarServerLog { false }), "var_server_log_off");
    EXPECT_STREQ(command_name(cmd::VarRetryBadRef { }), "var_retry_bad_ref");
}

TEST(Command, FallbackHoldsTheLine)
{
    Command c = cmd::Fallback { "x = 6 * 7" };
    ASSERT_TRUE(is_fallback(c));
    EXPECT_EQ(std::get<cmd::Fallback>(c).text, "x = 6 * 7");
}

TEST(Command, VarSetHoldsEachValueKind)
{
    cmd::VarSet a { "x", 1.5, std::string("m") };
    cmd::VarSet b { "x", 3LL, std::nullopt };
    cmd::VarSet c { "x", std::string("text"), std::nullopt };
    cmd::VarSet d { "x", cmd::NoneValue { }, std::nullopt };
    EXPECT_TRUE(std::holds_alternative<double>(a.value));
    EXPECT_TRUE(std::holds_alternative<long long>(b.value));
    EXPECT_TRUE(std::holds_alternative<std::string>(c.value));
    EXPECT_TRUE(std::holds_alternative<cmd::NoneValue>(d.value));
    EXPECT_EQ(*a.units, "m");
}

// Commands move between threads in queues; moving must not throw.
TEST(Command, IsNothrowMovable)
{
    EXPECT_TRUE(std::is_nothrow_move_constructible<Command>::value);
    EXPECT_TRUE(std::is_nothrow_move_assignable<Command>::value);
}
