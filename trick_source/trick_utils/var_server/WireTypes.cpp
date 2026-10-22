#include "trick/vs/WireTypes.hh"

namespace Trick
{
    namespace vs
    {

        const char* wire_type_name(WireType type) noexcept
        {
            switch (type)
            {
            case WireType::Void:
                return "void";
            case WireType::Character:
                return "char";
            case WireType::UnsignedCharacter:
                return "unsigned char";
            case WireType::String:
                return "string";
            case WireType::Short:
                return "short";
            case WireType::UnsignedShort:
                return "unsigned short";
            case WireType::Integer:
                return "int";
            case WireType::UnsignedInteger:
                return "unsigned int";
            case WireType::Long:
                return "long";
            case WireType::UnsignedLong:
                return "unsigned long";
            case WireType::Float:
                return "float";
            case WireType::Double:
                return "double";
            case WireType::Bitfield:
                return "bitfield";
            case WireType::UnsignedBitfield:
                return "unsigned bitfield";
            case WireType::LongLong:
                return "long long";
            case WireType::UnsignedLongLong:
                return "unsigned long long";
            case WireType::FilePtr:
                return "FILE *";
            case WireType::Boolean:
                return "bool";
            case WireType::WideCharacter:
                return "wchar_t";
            case WireType::WideString:
                return "wstring";
            case WireType::VoidPtr:
                return "void *";
            case WireType::Enumerated:
                return "enum";
            case WireType::Structured:
                return "struct";
            case WireType::Opaque:
                return "opaque";
            case WireType::Stl:
                return "STL";
            case WireType::BadRef:
                return "BAD_REF";
            }
            return "unknown";
        }

        bool is_wire_type(int32_t code) noexcept
        {
            return code >= static_cast<int32_t>(WireType::Void) && code <= static_cast<int32_t>(WireType::BadRef);
        }

    } // namespace vs
} // namespace Trick
