/*
PURPOSE: (Turn the lines a client sends into typed commands.)

The old server ran every line in the Python input processor. The parser
types a line only when it can prove Python would have done exactly the same
thing: the line is one call `trick.<name>(<literals>)` and SWIG, with
Trick's typemaps, accepts those arguments. Any other line becomes Fallback
and still runs in Python.

A batch (the lines one socket read returns) is all typed or all Fallback:
Python compiles a batch as one unit, so one line it cannot compile stops
every line, and an exception stops the lines after it. If any line in a
batch is not typed, the whole batch runs in Python unchanged.
*/

#ifndef TRICK_VS_COMMANDPARSER_HH
#define TRICK_VS_COMMANDPARSER_HH

#include "trick/vs/Command.hh"

#include <string>
#include <string_view>
#include <vector>

namespace Trick
{
    namespace vs
    {

        /**
         * Parse one line (no newline). Returns a typed command, or
         * cmd::Fallback holding the line.
         */
        Command parse_line(std::string_view line);

        /**
         * Parse a batch of lines separated by '\n'. Returns the typed commands
         * in order, skipping blank and comment-only lines, or a single
         * cmd::Fallback holding the whole batch.
         */
        std::vector<Command> parse_batch(std::string_view text);

        /**
         * A Python line that parse_line() turns back into `command`, for
         * example `trick.var_add("a.b", "m")`. For logs and tests. A Fallback
         * returns its text.
         */
        std::string to_python(const Command& command);

        /**
         * Split the names of var_send_once as the old server did
         * (std::getline on ','): no trimming, empty names kept, except that
         * a trailing comma adds no name.
         */
        std::vector<std::string> split_send_once_names(std::string_view names);

    } // namespace vs
} // namespace Trick

#endif
