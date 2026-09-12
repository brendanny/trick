// Independent real-MemoryManager checkpoint observations for both generators.
#include "metadata.cpp"
#include "native_probe.hh"

#include "trick/MemoryManager.hh"

#include <algorithm>
#include <fstream>
#include <iomanip>
#include <sstream>

namespace
{
    bool same(const ScalarModel& a, const ScalarModel& b, const icg_scalar::Aliases& x, const icg_scalar::Aliases& y)
    {
        return a.enabled == b.enabled && a.code == b.code && std::memcmp(&a.gain, &b.gain, sizeof(float)) == 0
            && a.counter == b.counter && std::equal(&a.flags[0][0], &a.flags[0][0] + 3, &b.flags[0][0])
            && std::equal(&a.flags[1][0], &a.flags[1][0] + 3, &b.flags[1][0])
            && std::memcmp(a.samples, b.samples, sizeof(a.samples)) == 0 && std::equal(a.label, a.label + 8, b.label)
            && std::equal(a.limits, a.limits + 2, b.limits) && x.flag == y.flag && x.code == y.code
            && std::memcmp(&x.gain, &y.gain, sizeof(float)) == 0 && x.counter == y.counter
            && std::equal(x.counts, x.counts + 2, y.counts);
    }

    void observe(const ScalarModel& m, const icg_scalar::Aliases& a)
    {
        std::cout << "[" << m.enabled << ',' << int(m.code) << ',' << std::setprecision(9) << m.gain << ',' << m.counter
                  << ",[";
        for (int i = 0; i < 2; ++i)
            for (int j = 0; j < 3; ++j)
                std::cout << (i || j ? "," : "") << m.flags[i][j];
        std::cout << "],[" << m.samples[0] << ',' << m.samples[1] << ',' << m.samples[2] << "],";
        probe::quoted(std::string(m.label, sizeof(m.label)));
        std::cout << ",[" << m.limits[0] << ',' << m.limits[1] << "]," << a.flag << ',' << int(a.code) << ',' << a.gain
                  << ',' << a.counter << ",[" << a.counts[0] << ',' << a.counts[1] << "]]";
    }
}

int main()
{
    try
    {
        ScalarModel m {};
        icg_scalar::Aliases a {};
        Trick::MemoryManager mm;
        probe::require(mm.declare_extern_var(&m, "ScalarModel scalars") == &m, "scalar registration failed");
        probe::require(mm.declare_extern_var(&a, "icg_scalar::Aliases aliases") == &a, "alias registration failed");
        mm.set_reduced_checkpoint(false);
        // MemoryManager does not initialize this option. Pin the compared format.
        mm.set_hexfloat_decimal_comment_checkpoint(false);
        std::cout << "{\"round_trips\":[";
        for (int pass = 0; pass < 2; ++pass)
        {
            const bool boundary = pass == 1;
            mm.set_expanded_arrays(boundary);
            mm.set_hexfloat_checkpoint(boundary);
            m.enabled = !boundary;
            m.code    = boundary ? std::numeric_limits<char>::min() : '\x7f';
            m.gain    = boundary ? std::numeric_limits<float>::max() : 1.25F;
            m.counter = boundary ? std::numeric_limits<long>::max() : (1L << 40) + 17;
            for (int i = 0; i < 2; ++i)
                for (int j = 0; j < 3; ++j)
                    m.flags[i][j] = (i + j + pass) % 2 == 0;
            m.samples[0] = boundary ? std::numeric_limits<float>::lowest() : -2.5F;
            m.samples[1] = boundary ? std::numeric_limits<float>::min() : 0.0F;
            m.samples[2] = boundary ? std::numeric_limits<float>::denorm_min() : 16777216.0F;
            std::memcpy(m.label, "Trick!\n", sizeof(m.label));
            m.limits[0]         = boundary ? std::numeric_limits<long>::min() : -(1L << 40) - 9;
            m.limits[1]         = boundary ? std::numeric_limits<long>::max() : (1L << 40) + 9;
            a.flag              = boundary;
            a.code              = boundary ? 'Z' : '\n';
            a.gain              = boundary ? -0.0F : -0.5F;
            a.counter           = -(1L << 40) - 17;
            a.counts[0]         = m.limits[0];
            a.counts[1]         = m.limits[1];
            const auto expected = m;
            const auto aliases  = a;
            std::ostringstream checkpoint;
            mm.write_checkpoint(checkpoint);
            std::ofstream(std::string("checkpoint-") + std::to_string(pass) + ".txt") << checkpoint.str();
            m.enabled = !m.enabled;
            m.code    = '?';
            m.gain    = 9.0F;
            m.counter = 0;
            for (auto& row : m.flags)
                for (bool& flag : row)
                    flag = !flag;
            std::fill(m.samples, m.samples + 3, 9.0F);
            std::fill(m.label, m.label + 8, '?');
            std::fill(m.limits, m.limits + 2, 0);
            a.flag    = !a.flag;
            a.code    = '?';
            a.gain    = 9.0F;
            a.counter = 0;
            std::fill(a.counts, a.counts + 2, 0);
            probe::require(!same(m, expected, a, aliases), "checkpoint control did not mutate storage");
            const int restored = mm.read_checkpoint_from_string(checkpoint.str().c_str());
            probe::require(restored == 0, "checkpoint restore failed");
            probe::require(same(m, expected, a, aliases), "scalar checkpoint values did not round trip");
            if (pass)
                std::cout << ',';
            observe(m, a);
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
