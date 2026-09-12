// Independent integer boundary observations through the actual MemoryManager.
#include "metadata.cpp"
#include "native_probe.hh"

#include "trick/MemoryManager.hh"

#include <algorithm>
#include <fstream>
#include <sstream>

namespace
{
    template <typename T> bool equal(const T& a, const T& b)
    {
        if constexpr (std::is_array<T>::value)
        {
            for (size_t i = 0; i < std::extent<T>::value; ++i)
                if (!equal(a[i], b[i]))
                    return false;
            return true;
        }
        else
            return a == b;
    }

    bool same(const IntegerModel& a, const IntegerModel& b, const icg_integer::Aliases& x,
              const icg_integer::Aliases& y)
    {
        return a.signed_code == b.signed_code && a.byte == b.byte && a.small == b.small
            && a.small_count == b.small_count && a.count == b.count && a.wide == b.wide && a.wide_count == b.wide_count
            && equal(a.signed_codes, b.signed_codes) && equal(a.bytes, b.bytes) && equal(a.smalls, b.smalls)
            && equal(a.small_counts, b.small_counts) && equal(a.counts, b.counts) && equal(a.wides, b.wides)
            && equal(a.wide_counts, b.wide_counts) && x.signed_code == y.signed_code && x.byte == y.byte
            && x.small == y.small && x.small_count == y.small_count && x.count == y.count && x.wide == y.wide
            && x.wide_count == y.wide_count && equal(x.wide_counts, y.wide_counts);
    }

    template <typename T> void value(const T& v)
    {
        if constexpr (std::is_array<T>::value)
        {
            std::cout << '[';
            for (size_t i = 0; i < std::extent<T>::value; ++i)
            {
                if (i)
                    std::cout << ',';
                value(v[i]);
            }
            std::cout << ']';
        }
        else
            std::cout << +v; // Promote character bytes numerically; retain unsigned 64-bit values.
    }

    template <typename... T> void observe(const T&... fields)
    {
        std::cout << '[';
        size_t index = 0;
        ((std::cout << (index++ ? "," : ""), value(fields)), ...);
        std::cout << ']';
    }
}

int main()
{
    try
    {
        IntegerModel m {};
        icg_integer::Aliases a {};
        Trick::MemoryManager mm;
        probe::require(mm.declare_extern_var(&m, "IntegerModel integers") == &m, "integer registration failed");
        probe::require(mm.declare_extern_var(&a, "icg_integer::Aliases aliases") == &a,
                       "integer alias registration failed");
        mm.set_reduced_checkpoint(false);
        // Pin the same formatting option as the companion scalar comparison.
        mm.set_hexfloat_decimal_comment_checkpoint(false);
        std::cout << "{\"round_trips\":[";
        for (int pass = 0; pass < 2; ++pass)
        {
            mm.set_expanded_arrays(pass != 0);
            m.signed_code            = pass ? SCHAR_MAX : SCHAR_MIN;
            m.byte                   = pass ? UCHAR_MAX : 128;
            m.small                  = pass ? SHRT_MAX : SHRT_MIN;
            m.small_count            = pass ? USHRT_MAX : 32768;
            m.count                  = pass ? ULONG_MAX : (1UL << 63) + 17;
            m.wide                   = pass ? LLONG_MAX : LLONG_MIN;
            m.wide_count             = pass ? ULLONG_MAX : (1ULL << 63) + 19;
            m.signed_codes[0]        = SCHAR_MIN;
            m.signed_codes[1]        = SCHAR_MAX;
            m.bytes[0]               = 0;
            m.bytes[1]               = 128;
            m.bytes[2]               = UCHAR_MAX;
            const short smalls[2][3] = {
                { SHRT_MIN, -1,    0        },
                { 1,        12345, SHRT_MAX }
            };
            std::copy(smalls[0], smalls[0] + 3, m.smalls[0]);
            std::copy(smalls[1], smalls[1] + 3, m.smalls[1]);
            m.small_counts[0]   = 0;
            m.small_counts[1]   = USHRT_MAX;
            m.counts[0]         = 0;
            m.counts[1]         = ULONG_MAX;
            m.wides[0]          = LLONG_MIN;
            m.wides[1]          = LLONG_MAX;
            m.wide_counts[0]    = 0;
            m.wide_counts[1]    = ULLONG_MAX;
            a.signed_code       = pass ? SCHAR_MIN : SCHAR_MAX;
            a.byte              = pass ? 128 : UCHAR_MAX;
            a.small             = pass ? SHRT_MIN : SHRT_MAX;
            a.small_count       = USHRT_MAX;
            a.count             = ULONG_MAX;
            a.wide              = pass ? LLONG_MIN : LLONG_MAX;
            a.wide_count        = ULLONG_MAX;
            a.wide_counts[0]    = (1ULL << 63) + 23;
            a.wide_counts[1]    = ULLONG_MAX;
            const auto expected = m;
            const auto aliases  = a;
            std::ostringstream checkpoint;
            mm.write_checkpoint(checkpoint);
            std::ofstream(std::string("checkpoint-") + std::to_string(pass) + ".txt") << checkpoint.str();
            m.signed_code = m.byte = m.small = m.small_count = 1;
            m.count = m.wide = m.wide_count = 1;
            std::fill(m.signed_codes, m.signed_codes + 2, 1);
            std::fill(m.bytes, m.bytes + 3, 1);
            for (auto& row : m.smalls)
                std::fill(row, row + 3, 2);
            std::fill(m.small_counts, m.small_counts + 2, 1);
            std::fill(m.counts, m.counts + 2, 1);
            std::fill(m.wides, m.wides + 2, 1);
            std::fill(m.wide_counts, m.wide_counts + 2, 1);
            a.signed_code = a.byte = a.small = a.small_count = 1;
            a.count = a.wide = a.wide_count = 1;
            std::fill(a.wide_counts, a.wide_counts + 2, 1);
            probe::require(!same(m, expected, a, aliases), "integer checkpoint control did not mutate storage");
            const int restored = mm.read_checkpoint_from_string(checkpoint.str().c_str());
            probe::require(restored == 0, "integer checkpoint restore failed");
            probe::require(same(m, expected, a, aliases), "integer checkpoint values did not round trip");
            if (pass)
                std::cout << ',';
            observe(m.signed_code, m.byte, m.small, m.small_count, m.count, m.wide, m.wide_count, m.signed_codes,
                    m.bytes, m.smalls, m.small_counts, m.counts, m.wides, m.wide_counts, a.signed_code, a.byte, a.small,
                    a.small_count, a.count, a.wide, a.wide_count, a.wide_counts);
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
