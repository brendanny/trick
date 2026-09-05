#include "TypeNode.hh"

namespace trick::icg
{

    llvm::json::Object TypeNode::json() const
    {
        using llvm::json::Array;
        using llvm::json::Object;
        const char* name = "builtin";
        switch (kind)
        {
        case TypeKind::Builtin:
            break;
        case TypeKind::Record:
            name = "record";
            break;
        case TypeKind::Alias:
            name = "alias";
            break;
        case TypeKind::Pointer:
            name = "pointer";
            break;
        case TypeKind::LValueReference:
            name = "lvalue_reference";
            break;
        case TypeKind::RValueReference:
            name = "rvalue_reference";
            break;
        case TypeKind::Array:
            name = "array";
            break;
        }
        Object result {
            { "id",           id                                                                                      },
            { "kind",         name                                                                                    },
            { "spelling",     spelling                                                                                },
            { "canonical_id", canonicalID                                                                             },
            { "qualifiers",   Object { { "const", isConst }, { "volatile", isVolatile }, { "restrict", isRestrict } } }
        };
        switch (kind)
        {
        case TypeKind::Record:
        case TypeKind::Alias:
            result["declaration_id"] = declarationID;
            break;
        case TypeKind::Pointer:
        case TypeKind::LValueReference:
        case TypeKind::RValueReference:
            result["pointee_id"] = childID;
            break;
        case TypeKind::Array:
            result["element_id"] = childID;
            result["extents"]    = extent ? Array { *extent } : Array { "incomplete" };
            break;
        case TypeKind::Builtin:
            break;
        }
        return result;
    }

} // namespace trick::icg
