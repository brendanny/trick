#include "trick/vs/Snapshot.hh"

#include <cstring>
#include <limits>
#include <stdexcept>

namespace Trick
{
    namespace vs
    {

        void Snapshot::clear() noexcept
        {
            _values.clear();
            _bytes.clear();
            time_tics = 0;
            time_s    = 0.0;
        }

        void Snapshot::reserve(std::size_t values, std::size_t bytes)
        {
            _values.reserve(values);
            _bytes.reserve(bytes);
        }

        std::size_t Snapshot::add(const FieldDesc& desc, const void* data)
        {
            const std::size_t n      = desc.byte_size();
            const std::size_t offset = _bytes.size();
            if (offset + n > std::numeric_limits<uint32_t>::max())
            {
                throw std::length_error("variable server snapshot larger than 4 GiB");
            }
            StagedValue v;
            v.desc   = desc;
            v.offset = static_cast<uint32_t>(offset);
            _bytes.resize(offset + n);
            if (n != 0)
            {
                std::memcpy(_bytes.data() + offset, data, n);
            }
            _values.push_back(v);
            return _values.size() - 1;
        }

        std::size_t Snapshot::add_bad_ref()
        {
            const int32_t zero = 0;
            return add(FieldDesc::bad_ref(), &zero);
        }

        const unsigned char* Snapshot::data(std::size_t index) const
        {
            return _bytes.data() + _values.at(index).offset;
        }

    } // namespace vs
} // namespace Trick
