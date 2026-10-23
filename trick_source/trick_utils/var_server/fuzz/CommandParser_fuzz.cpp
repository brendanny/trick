// libFuzzer target for the command parser.
//
// Properties checked on every input:
//  1. parse_batch() and parse_line() do not crash (ASan, UBSan).
//  2. A batch is all typed or one Fallback that holds the input unchanged.
//  3. Every typed command survives to_python() -> parse_line() unchanged.
//
// Run: vs_command_parser_fuzz -dict=command_parser.dict corpus/command_parser

#include "trick/vs/CommandParser.hh"

#include <cstdint>
#include <cstdlib>
#include <string>
#include <string_view>

using namespace Trick::vs;

namespace
{
    void check_round_trip(const Command& c)
    {
        if (is_fallback(c))
            return;
        const std::string py = to_python(c);
        const Command back   = parse_line(py);
        if (is_fallback(back) || back.index() != c.index() || to_python(back) != py)
            std::abort();
    }
} // namespace

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size)
{
    const std::string_view text(reinterpret_cast<const char*>(data), size);

    const auto batch = parse_batch(text);
    if (batch.size() == 1 && is_fallback(batch[0]))
    {
        if (std::get<cmd::Fallback>(batch[0]).text != text)
            std::abort();
    }
    else
    {
        for (const Command& c : batch)
        {
            if (is_fallback(c))
                std::abort();
            check_round_trip(c);
        }
    }

    // One line on its own.
    const std::string_view line = text.substr(0, text.find('\n'));
    const Command c             = parse_line(line);
    if (is_fallback(c))
    {
        if (std::get<cmd::Fallback>(c).text != line)
            std::abort();
    }
    else
    {
        check_round_trip(c);
    }

    // The names of var_send_once never crash the splitter.
    (void)split_send_once_names(text);
    return 0;
}
