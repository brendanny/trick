/*
PURPOSE: (The values of one session's variable list at one moment.)

A Snapshot is filled by one thread (the main thread or the session thread,
by copy mode) and then read by the session thread. Values are stored back to
back in one byte array, so a snapshot can be reused without new allocations
once it has reached its working size.
*/

#ifndef TRICK_VS_SNAPSHOT_HH
#define TRICK_VS_SNAPSHOT_HH

#include "trick/vs/FieldDesc.hh"

#include <cstddef>
#include <cstdint>
#include <vector>

namespace Trick
{
    namespace vs
    {

        /** One value in a Snapshot. */
        struct StagedValue
        {
                FieldDesc desc;
                uint32_t offset = 0; ///< into Snapshot::bytes()
        };

        class Snapshot
        {
            public:
                /** Sim time of the copy, in tics. */
                long long time_tics = 0;
                /** Sim time of the copy, in seconds. The variable "time" sends this. */
                double time_s = 0.0;
                /** Increases by one each time the snapshot is filled. */
                uint64_t sequence = 0;

                /** Remove all values. Keeps the capacity. */
                void clear() noexcept;

                void reserve(std::size_t values, std::size_t bytes);

                /**
                 * Append a value. Copies desc.byte_size() bytes from `data`.
                 * Returns the value's index.
                 */
                std::size_t add(const FieldDesc& desc, const void* data);

                /** Append the BAD_REF value: type 25, 4 bytes, all zero. */
                std::size_t add_bad_ref();

                std::size_t size() const noexcept { return _values.size(); }

                bool empty() const noexcept { return _values.empty(); }

                const StagedValue& value(std::size_t index) const { return _values.at(index); }

                /** The bytes of value `index`; there are value(index).desc.byte_size() of them. */
                const unsigned char* data(std::size_t index) const;

                /** All value bytes, back to back. */
                const std::vector<unsigned char>& bytes() const noexcept { return _bytes; }

            private:
                std::vector<StagedValue> _values;
                std::vector<unsigned char> _bytes;
        };

    } // namespace vs
} // namespace Trick

#endif
