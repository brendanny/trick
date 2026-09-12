// Actual legacy runtime limitations; this never includes candidate metadata.
#include "metadata.cpp"
#include "native_probe.hh"

#include "trick/MemoryManager.hh"

#include <clocale>
#include <fstream>
#include <sstream>

int main()
{
    try
    {
        probe::require(std::setlocale(LC_ALL, "C") != nullptr, "C locale unavailable");
        Trick::MemoryManager mm;
        mm.set_reduced_checkpoint(false);
        mm.set_expanded_arrays(false);
        mm.set_hexfloat_checkpoint(false);
        mm.set_hexfloat_decimal_comment_checkpoint(false);
#ifdef PROBE_WIDE
        WideModel m { };
        probe::require(mm.declare_extern_var(&m, "WideModel wide") == &m, "wide registration failed");
        const int assigned = mm.read_checkpoint_from_string("wide.code = 20013;");
        probe::require(assigned == 0, "wide numeric assignment failed");
        const auto stored = static_cast<long long>(m.code);
        m.code            = L'A';
        m.text[0]         = L'B';
        m.text[1]         = 0;
        std::ostringstream checkpoint;
        mm.write_checkpoint(checkpoint);
        std::ofstream("checkpoint.txt") << checkpoint.str();
        std::cout << "{\"input\":20013,\"stored\":" << stored << ",\"code_kind\":";
        probe::quoted(probe::kind(attrWideModel[0].type));
        std::cout << ",\"bare_character\":"
                  << (checkpoint.str().find("wide.code = A;") != std::string::npos ? "true" : "false") << "}\n";
#else
        Utf32Model m {
            0x1f600, { U'A', 0x10ffff }
        };
        probe::require(mm.declare_extern_var(&m, "Utf32Model utf32") == &m, "UTF-32 registration failed");
        std::ostringstream checkpoint;
        mm.write_checkpoint(checkpoint);
        std::ofstream("checkpoint.txt") << checkpoint.str();
        // The empty legacy table omits both native fields from the checkpoint.
        // Do not feed the resulting comments-only file to the input parser.
        std::cout << "{\"rows\":" << sizeof(attrUtf32Model) / sizeof(ATTRIBUTES) - 1 << ",\"checkpoint_has_field\":"
                  << (checkpoint.str().find("utf32.") != std::string::npos ? "true" : "false")
                  << ",\"code\":" << +m.code << ",\"text\":[" << +m.text[0] << ',' << +m.text[1] << "]}\n";
#endif
        return 0;
    }
    catch (const std::exception& error)
    {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
