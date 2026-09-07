#pragma once

#include "llvm/Support/JSON.h"

#include <cstdint>
#include <optional>
#include <string>

namespace trick::icg
{

    enum class TypeKind
    {
        Builtin,
        Record,
        Enum,
        Alias,
        Pointer,
        LValueReference,
        RValueReference,
        Array
    };

    // Process-owned structural data. Frontend pointers are confined to TypeGraph.
    // Qualifiers belong to this layer, not to its pointee or an alias's underlying type.
    struct TypeNode
    {
            TypeKind kind = TypeKind::Builtin;
            std::string id;
            std::string spelling;
            std::string canonicalID;
            bool isConst    = false;
            bool isVolatile = false;
            bool isRestrict = false;
            std::string declarationID;
            std::string childID;
            // Array nodes represent one dimension. nullopt means an incomplete extent.
            std::optional<uint64_t> extent;

            llvm::json::Object json() const;
    };

} // namespace trick::icg
