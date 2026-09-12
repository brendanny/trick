// Native observations for the audited scalar, array, enum and structured metadata fixtures.
// Include after the unmodified, materialized legacy translation unit.
#include <climits>
#include <cstring>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

namespace probe
{
    inline void require(bool condition, const std::string& message)
    {
        if (!condition)
            throw std::runtime_error(message);
    }

    inline void quoted(const std::string& value)
    {
        static const char hex[] = "0123456789abcdef";
        std::cout << '"';
        for (unsigned char ch : value)
        {
            if (ch == '"' || ch == '\\')
                std::cout << '\\' << ch;
            else if (ch < 32)
                std::cout << "\\u00" << hex[ch >> 4] << hex[ch & 15];
            else
                std::cout << ch;
        }
        std::cout << '"';
    }

    struct Field
    {
            const char* name;
            size_t size;
            size_t offset;
            size_t width;
            std::vector<size_t> dimensions;
            size_t total_size;
            const void* attributes = nullptr;
    };

    template <typename Value, size_t... I> Field member(const char* name, size_t offset, std::index_sequence<I...>)
    {
        return { name,
                 sizeof(typename std::remove_all_extents<Value>::type),
                 offset,
                 0,
                 { std::extent<Value, I>::value... },
                 sizeof(Value) };
    }

    template <typename Value> Field member(const char* name, size_t offset)
    {
        return member<Value>(name, offset, std::make_index_sequence<std::rank<Value>::value> {});
    }

    template <typename Value> Field structured_member(const char* name, size_t offset, const ATTRIBUTES* attributes)
    {
        auto field       = member<Value>(name, offset);
        field.attributes = attributes;
        return field;
    }

    inline void dimensions(const std::vector<size_t>& values)
    {
        std::cout << '[';
        for (size_t i = 0; i < values.size(); ++i)
        {
            if (i)
                std::cout << ',';
            std::cout << values[i];
        }
        std::cout << ']';
    }

    // This intentionally supports only the unsigned bitfields in the audited
    // standard-layout, trivially-copyable fixture on little-endian hosts.
    template <typename T, typename Value, typename Setter> Field bitfield(const char* name, Setter set)
    {
        static_assert(CHAR_BIT == 8, "probe requires eight-bit bytes");
        static_assert(std::is_standard_layout<T>::value && std::is_trivially_copyable<T>::value, "fixture layout");
        static_assert(std::is_unsigned<Value>::value, "unsigned fixture bitfield");
        unsigned int endian = 1;
        require(*reinterpret_cast<unsigned char*>(&endian) == 1, "bitfield probe requires little endian");
        T object {};
        std::memset(static_cast<void*>(&object), 0, sizeof(object));
        set(object, std::numeric_limits<Value>::max());
        const auto* bytes = reinterpret_cast<const unsigned char*>(&object);
        size_t first      = sizeof(T) * CHAR_BIT;
        size_t last       = 0;
        size_t width      = 0;
        for (size_t bit = 0; bit < sizeof(T) * CHAR_BIT; ++bit)
        {
            if (bytes[bit / CHAR_BIT] & (1u << (bit % CHAR_BIT)))
            {
                if (width == 0)
                    first = bit;
                last = bit;
                ++width;
            }
        }
        require(width != 0 && last - first + 1 == width, std::string(name) + ": noncontiguous native bitfield");
        return { name, sizeof(Value), first, width, {}, sizeof(Value) };
    }

    inline const char* kind(TRICK_TYPE type)
    {
        switch (type)
        {
        case TRICK_BOOLEAN:
            return "TRICK_BOOLEAN";
        case TRICK_CHARACTER:
            return "TRICK_CHARACTER";
        case TRICK_UNSIGNED_CHARACTER:
            return "TRICK_UNSIGNED_CHARACTER";
        case TRICK_SHORT:
            return "TRICK_SHORT";
        case TRICK_UNSIGNED_SHORT:
            return "TRICK_UNSIGNED_SHORT";
        case TRICK_UNSIGNED_LONG:
            return "TRICK_UNSIGNED_LONG";
        case TRICK_LONG_LONG:
            return "TRICK_LONG_LONG";
        case TRICK_UNSIGNED_LONG_LONG:
            return "TRICK_UNSIGNED_LONG_LONG";
        case TRICK_FLOAT:
            return "TRICK_FLOAT";
        case TRICK_LONG:
            return "TRICK_LONG";
        case TRICK_INTEGER:
            return "TRICK_INTEGER";
        case TRICK_UNSIGNED_INTEGER:
            return "TRICK_UNSIGNED_INTEGER";
        case TRICK_DOUBLE:
            return "TRICK_DOUBLE";
        case TRICK_STRUCTURED:
            return "TRICK_STRUCTURED";
        case TRICK_UNSIGNED_BITFIELD:
            return "TRICK_UNSIGNED_BITFIELD";
        default:
            throw std::runtime_error("unsupported compiled ATTRIBUTES type");
        }
    }

    inline void defaults(const ATTRIBUTES& row, const void* attributes = nullptr)
    {
        require(row.name && row.type_name && row.units && row.alias && row.user_defined && row.des,
                "null ATTRIBUTES string");
        require(!*row.alias && !*row.user_defined && row.io > 0 && row.io <= 15 && row.range_min == 0
                    && row.range_max == 0 && row.language == Language_CPP && (row.mods == 0 || row.mods == 4)
                    && row.attr == attributes && row.num_index >= 0 && row.num_index <= TRICK_MAX_INDEX
                    && row.stl_type == TRICK_STL_UNKNOWN && row.stl_elem_type == TRICK_NUMBER_OF_TYPES
                    && !row.stl_elem_type_name && !row.checkpoint_stl && !row.post_checkpoint_stl && !row.restore_stl
                    && !row.clear_stl && !row.get_stl_size && !row.get_stl_element && !row.set_stl_element,
                std::string(row.name) + ": unsupported compiled ATTRIBUTES metadata");
        const bool bits = row.type == TRICK_UNSIGNED_BITFIELD || row.type == TRICK_BITFIELD;
        require(!bits || row.num_index == 0, "bitfield cannot have array dimensions");
        for (int i = 0; i < TRICK_MAX_INDEX; ++i)
        {
            if (bits && i == 0)
                continue;
            require(row.index[i].start == 0, "unexpected array index start");
            require(i < row.num_index ? row.index[i].size > 0 : row.index[i].size == 0,
                    "invalid active or unused array extent");
        }
    }

    template <typename T, size_t N>
    void record(const char* name, const char* symbol, const ATTRIBUTES (&rows)[N], size_t legacySize,
                const std::vector<Field>& fields)
    {
        static_assert(std::is_standard_layout<T>::value, "offsetof requires standard layout");
        require(N == fields.size() + 1, std::string(name) + ": compiled field count differs");
        const auto& sentinel = rows[N - 1];
        defaults(sentinel);
        require(!*sentinel.name && !*sentinel.type_name && std::string(sentinel.units) == "1" && !*sentinel.des
                    && sentinel.io == 15 && sentinel.mods == 0 && sentinel.type == TRICK_VOID && sentinel.size == 0
                    && sentinel.offset == 0 && sentinel.num_index == 0 && sentinel.index[0].size == 0
                    && sentinel.index[0].start == 0,
                "invalid compiled ATTRIBUTES sentinel");
        std::cout << "{\"name\":";
        quoted(name);
        std::cout << ",\"size_bytes\":" << sizeof(T) << ",\"alignment_bytes\":" << alignof(T)
                  << ",\"legacy_size_bytes\":" << legacySize << ",\"fields\":[";
        for (size_t i = 0; i + 1 < N; ++i)
        {
            const auto& row = rows[i];
            defaults(row, fields[i].attributes);
            require(*row.name, "premature compiled ATTRIBUTES sentinel");
            if (i)
                std::cout << ',';
            std::cout << "{\"name\":";
            quoted(row.name);
            std::cout << ",\"type\":";
            quoted(row.type_name);
            std::cout << ",\"kind\":";
            quoted(kind(row.type));
            std::cout << ",\"units\":";
            quoted(row.units);
            std::cout << ",\"io\":" << row.io << ",\"mods\":" << row.mods << ",\"description\":";
            quoted(row.des);
            std::cout << ",\"units_map_units\":";
            quoted(Trick::UnitsMap::units_map()->get_units(std::string(symbol) + "_" + row.name));
            std::vector<size_t> extents;
            for (int j = 0; j < row.num_index; ++j)
                extents.push_back(row.index[j].size);
            std::cout << ",\"size_bytes\":" << row.size << ",\"offset_bytes\":" << row.offset
                      << ",\"width\":" << (row.num_index ? 0 : row.index[0].size) << ",\"shift\":" << row.index[0].start
                      << ",\"dimensions\":";
            dimensions(extents);
            std::cout << '}';
        }
        std::cout << "],\"native_fields\":[";
        for (size_t i = 0; i < fields.size(); ++i)
        {
            if (i)
                std::cout << ',';
            const auto& field = fields[i];
            std::cout << "{\"name\":";
            quoted(field.name);
            std::cout << ",\"size_bytes\":" << field.size << ",\"offset_bits\":" << field.offset
                      << ",\"width\":" << field.width << ",\"total_size_bytes\":" << field.total_size
                      << ",\"dimensions\":";
            dimensions(field.dimensions);
            std::cout << '}';
        }
        std::cout << "]}";
    }

    template <typename T, size_t N>
    void enumeration(const char* name, const ENUM_ATTR (&rows)[N], size_t legacySize, const std::vector<T>& values)
    {
        require(N == values.size() + 1, "compiled enumerator count differs");
        require(rows[N - 1].label && !*rows[N - 1].label && rows[N - 1].value == 0 && rows[N - 1].mods == 0,
                "invalid compiled enum sentinel");
        std::cout << "{\"name\":";
        quoted(name);
        std::cout << ",\"size_bytes\":" << sizeof(T) << ",\"alignment_bytes\":" << alignof(T)
                  << ",\"legacy_size_bytes\":" << legacySize << ",\"signed\":"
                  << (std::is_signed<typename std::underlying_type<T>::type>::value ? "true" : "false")
                  << ",\"rows\":[";
        for (size_t i = 0; i + 1 < N; ++i)
        {
            require(rows[i].label && *rows[i].label, "premature compiled enum sentinel");
            if (i)
                std::cout << ',';
            std::cout << "{\"label\":";
            quoted(rows[i].label);
            // The reference ENUM_ATTR values fit int; reject wider future fixtures
            // in Python before generating this intentionally narrow probe.
            std::cout << ",\"value\":\"" << rows[i].value << "\",\"mods\":" << rows[i].mods << ",\"native_value\":\""
                      << static_cast<long long>(values[i]) << "\"}";
        }
        std::cout << "]}";
    }
} // namespace probe
