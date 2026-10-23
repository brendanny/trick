// libFuzzer target for the encoders.
//
// The input picks a FieldDesc and its bytes. Only descriptions that
// validate() accepts are encoded, as the session does. Checked properties:
//  1. append_ascii_value() and the binary encoder do not crash (ASan, UBSan).
//  2. A binary variable takes exactly binary_var_size() bytes.
//  3. Every message is at most max_message bytes.

#include "trick/vs/AsciiEncoder.hh"
#include "trick/vs/BinaryEncoder.hh"
#include "trick/vs/Packetizer.hh"

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

using namespace Trick::vs;

namespace
{
    class Scale : public Conversion
    {
        public:
            explicit Scale(double s)
                : _s(s)
            {
            }

            double apply(double v) const override { return v * _s; }

        private:
            double _s;
    };

    struct Reader
    {
            const uint8_t* p;
            size_t n;

            template <class T> T take()
            {
                T v {};
                const size_t k = n < sizeof v ? n : sizeof v;
                std::memcpy(&v, p, k);
                p += k;
                n -= k;
                return v;
            }
    };
} // namespace

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size)
{
    Reader r { data, size };
    const uint8_t flags = r.take<uint8_t>();
    const int nvars     = 1 + (r.take<uint8_t>() % 4);

    Snapshot snapshot;
    std::vector<std::string> names;
    for (int i = 0; i < nvars; ++i)
    {
        FieldDesc d;
        d.type           = static_cast<WireType>(r.take<uint8_t>() % 27);
        d.element_size   = r.take<uint8_t>() % 17;
        d.count          = r.take<uint16_t>() % 3000;
        d.text           = static_cast<Text>(r.take<uint8_t>() % 3);
        d.bitfield.start = r.take<uint8_t>() % 70;
        d.bitfield.width = r.take<uint8_t>() % 70;
        d.units_dashdash = (flags & 0x10) != 0;
        if (validate(d) != nullptr || d.byte_size() > (1u << 20))
            continue;
        std::vector<unsigned char> bytes(d.byte_size());
        for (unsigned char& b : bytes)
            b = r.take<uint8_t>();
        snapshot.add(d, bytes.data());
        names.push_back(std::string(r.take<uint8_t>() % 40, 'n'));
    }

    Scale scale(-1e10);
    std::vector<VarFormat> formats;
    for (const std::string& n : names)
    {
        VarFormat f;
        f.name       = n;
        f.conversion = (flags & 0x20) ? &scale : nullptr;
        f.units      = (flags & 0x40) ? "m" : "";
        formats.push_back(f);
    }

    for (size_t i = 0; i < snapshot.size(); ++i)
    {
        std::string out;
        append_binary_var(out, names[i], snapshot.value(i).desc, snapshot.data(i), flags & 1, flags & 2);
        if (out.size() != binary_var_size(names[i], snapshot.value(i).desc, flags & 1))
            std::abort();
    }

    Packets packets;
    encode_ascii(packets, snapshot, formats, MessageType::VarList);
    encode_binary(packets, snapshot, formats, MessageType::VarList, flags & 1, flags & 2);
    for (const std::string& m : packets.messages)
        if (m.size() > max_message)
            std::abort();
    return 0;
}
