// Independent char16_t code-unit observations through the real MemoryManager.
#include "metadata.cpp"
#include "native_probe.hh"

#include "trick/MemoryManager.hh"

#include <algorithm>
#include <clocale>
#include <fstream>
#include <sstream>

namespace
{
    bool same(const Utf16Model& m, const Utf16Model& expected, const icg_utf16::Aliases& a,
              const icg_utf16::Aliases& aliases)
    {
        return m.code == expected.code && m.maximum == expected.maximum && std::equal(m.text, m.text + 6, expected.text)
            && std::equal(m.grid[0], m.grid[0] + 3, expected.grid[0])
            && std::equal(m.grid[1], m.grid[1] + 3, expected.grid[1]) && a.code == aliases.code
            && a.tail == aliases.tail && std::equal(a.text, a.text + 4, aliases.text);
    }

    template <size_t N> void units(const char16_t (&values)[N])
    {
        std::cout << '[';
        for (size_t i = 0; i < N; ++i)
            std::cout << (i ? "," : "") << static_cast<unsigned int>(values[i]);
        std::cout << ']';
    }
}

int main()
{
    try
    {
        probe::require(std::setlocale(LC_ALL, "C") != nullptr, "C locale unavailable");
        Utf16Model m { };
        icg_utf16::Aliases a { };
        Trick::MemoryManager mm;
        probe::require(mm.declare_extern_var(&m, "Utf16Model utf16") == &m, "UTF-16 registration failed");
        probe::require(mm.declare_extern_var(&a, "icg_utf16::Aliases aliases") == &a,
                       "UTF-16 alias registration failed");
        mm.set_reduced_checkpoint(false);
        mm.set_hexfloat_checkpoint(false);
        mm.set_hexfloat_decimal_comment_checkpoint(false);
        std::cout << "{\"round_trips\":[";
        for (int pass = 0; pass < 2; ++pass)
        {
            mm.set_expanded_arrays(pass != 0);
            m.code                 = pass ? 0xffff : 0x4e2d;
            const char16_t text[6] = { u'A', 0, 0x4e2d, 0xd83d, 0xde00, 0xffff };
            std::copy(text, text + 6, m.text);
            if (pass)
                std::reverse(m.text, m.text + 6);
            const char16_t grid[2][3] = {
                { 0,      0x7fff, 0x8000 },
                { 0xd800, 0xdfff, 0xffff }
            };
            std::copy(grid[0], grid[0] + 3, m.grid[0]);
            std::copy(grid[1], grid[1] + 3, m.grid[1]);
            m.maximum                    = 0xffff;
            a.code                       = pass ? 0xd800 : 0;
            const char16_t alias_text[4] = { u'a', 0x0301, 0, 0xffff };
            std::copy(alias_text, alias_text + 4, a.text);
            a.tail              = pass ? 0 : 0xdfff;
            const auto expected = m;
            const auto aliases  = a;
            std::ostringstream checkpoint;
            mm.write_checkpoint(checkpoint);
            std::ofstream(std::string("checkpoint-") + std::to_string(pass) + ".txt") << checkpoint.str();
            m.code = m.maximum = a.code = a.tail = 1;
            std::fill(m.text, m.text + 6, 1);
            for (auto& row : m.grid)
                std::fill(row, row + 3, 1);
            std::fill(a.text, a.text + 4, 1);
            probe::require(!same(m, expected, a, aliases), "UTF-16 checkpoint control did not mutate storage");
            const int restored = mm.read_checkpoint_from_string(checkpoint.str().c_str());
            probe::require(restored == 0, "UTF-16 checkpoint restore failed");
            probe::require(same(m, expected, a, aliases), "UTF-16 checkpoint values did not round trip");
            if (pass)
                std::cout << ',';
            std::cout << '[' << +m.code << ',';
            units(m.text);
            std::cout << ",[";
            units(m.grid[0]);
            std::cout << ',';
            units(m.grid[1]);
            std::cout << "]," << +m.maximum << ',' << +a.code << ',';
            units(a.text);
            std::cout << ',' << +a.tail << ']';
        }
        std::cout << "]}\n";
        return 0;
    }
    catch (const std::exception& error)
    {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
