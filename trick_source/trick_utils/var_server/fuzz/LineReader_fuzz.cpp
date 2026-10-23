// libFuzzer target for the line reader.
//
// The input is split into chunks (the first byte of each chunk gives its
// length), as recv() might split a stream. Checked properties:
//  1. Every batch ends with a newline, holds no '\r', and is at most
//     limit + 1 bytes long.
//  2. Bytes are never invented: batches plus discarded plus pending plus the
//     removed '\r' bytes add up to the input.
//  3. With a limit no line reaches, the batches are the input's complete
//     lines, '\r' removed, whatever the chunking.

#include "trick/vs/LineReader.hh"

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <string>

using namespace Trick::vs;

namespace
{
    std::string run(const uint8_t* data, size_t size, std::size_t limit, std::size_t& discarded, std::size_t& pending)
    {
        LineReader reader(limit);
        std::string all, batch;
        size_t i = 0;
        while (i < size)
        {
            const size_t n = std::min<size_t>(1 + data[i] % 64, size - i);
            reader.append(std::string_view(reinterpret_cast<const char*>(data + i), n));
            i += n;
            while (reader.next_batch(batch))
            {
                if (batch.empty() || batch.back() != '\n' || batch.find('\r') != std::string::npos
                    || batch.size() > limit + 1)
                    std::abort();
                all += batch;
            }
            discarded += reader.take_discarded();
        }
        pending = reader.pending();
        return all;
    }
} // namespace

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size)
{
    const std::string input(reinterpret_cast<const char*>(data), size);
    const std::size_t crs = static_cast<std::size_t>(std::count(input.begin(), input.end(), '\r'));

    // A small limit, so overlong lines happen.
    std::size_t discarded = 0, pending = 0;
    const std::string small = run(data, size, 16, discarded, pending);
    if (small.size() + discarded + pending > size || small.size() + discarded + pending + crs < size)
        std::abort();

    // A limit nothing reaches: the result is every complete line.
    discarded = pending = 0;
    const std::string big = run(data, size, size + 1, discarded, pending);
    std::string expected  = input.substr(0, input.rfind('\n') == std::string::npos ? 0 : input.rfind('\n') + 1);
    expected.erase(std::remove(expected.begin(), expected.end(), '\r'), expected.end());
    if (discarded != 0 || big != expected)
        std::abort();
    return 0;
}
