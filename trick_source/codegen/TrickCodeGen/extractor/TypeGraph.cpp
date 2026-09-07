#include "TypeGraph.hh"

#include "clang/AST/DeclCXX.h"

namespace trick::icg
{

    TypeGraph::TypeGraph(Facts& facts, clang::ASTContext& context,
                         std::function<std::string(const clang::NamedDecl*)> requestDeclaration,
                         std::function<void(const clang::Decl*, const std::string&)> unsupported)
        : facts(facts)
        , context(context)
        , requestDeclaration(std::move(requestDeclaration))
        , unsupported(std::move(unsupported))
    {
    }

    std::string TypeGraph::get(clang::QualType value, const clang::Decl* owner)
    {
        const void* key = value.getAsOpaquePtr();
        auto known      = interned.find(key);
        if (known != interned.end())
            return known->second;

        // Tag keywords and redundant parentheses are syntax, not graph layers.
        const auto* raw = value.getTypePtr();
        if (const auto* elaborated = llvm::dyn_cast<clang::ElaboratedType>(raw))
            return get(context.getQualifiedType(elaborated->getNamedType(), value.getLocalQualifiers()), owner);
        if (const auto* paren = llvm::dyn_cast<clang::ParenType>(raw))
            return get(context.getQualifiedType(paren->getInnerType(), value.getLocalQualifiers()), owner);

        TypeNode node;
        auto policy                    = context.getPrintingPolicy();
        policy.SuppressTagKeyword      = true;
        policy.AnonymousTagLocations   = false;
        policy.SuppressInlineNamespace = false;
        node.spelling                  = value.getAsString(policy);
        const auto qualifiers          = value.getLocalQualifiers();
        if (qualifiers.hasNonFastQualifiers())
        {
            unsupported(owner, "Non-CVR qualifiers are not yet represented: " + node.spelling);
            return { };
        }
        node.isConst    = qualifiers.hasConst();
        node.isVolatile = qualifiers.hasVolatile();
        node.isRestrict = qualifiers.hasRestrict();
        std::string identity;
        if (const auto* builtin = llvm::dyn_cast<clang::BuiltinType>(raw))
        {
            identity = "builtin:" + builtin->getName(policy).str();
        }
        else if (const auto* record = llvm::dyn_cast<clang::RecordType>(raw))
        {
            node.kind          = TypeKind::Record;
            node.declarationID = requestDeclaration(record->getDecl());
            identity           = "record:" + node.declarationID;
        }
        else if (const auto* alias = llvm::dyn_cast<clang::TypedefType>(raw))
        {
            node.kind          = TypeKind::Alias;
            node.declarationID = requestDeclaration(alias->getDecl());
            identity           = "alias:" + node.declarationID;
        }
        else if (const auto* pointer = llvm::dyn_cast<clang::PointerType>(raw))
        {
            node.kind    = TypeKind::Pointer;
            node.childID = get(pointer->getPointeeType(), owner);
            identity     = "pointer:" + node.childID;
        }
        else if (const auto* reference = llvm::dyn_cast<clang::ReferenceType>(raw))
        {
            node.kind
                = llvm::isa<clang::LValueReferenceType>(raw) ? TypeKind::LValueReference : TypeKind::RValueReference;
            node.childID = get(reference->getPointeeType(), owner);
            identity     = (node.kind == TypeKind::LValueReference ? "lref:" : "rref:") + node.childID;
        }
        else if (const auto* array = llvm::dyn_cast<clang::ArrayType>(raw))
        {
            node.kind = TypeKind::Array;
            // C++ array qualification belongs to the elements. Clang may store it
            // on the QualType wrapper (especially through an alias); normalize both
            // spellings to the same element-qualified structural graph.
            node.childID = get(context.getQualifiedType(array->getElementType(), qualifiers), owner);
            node.isConst = node.isVolatile = node.isRestrict = false;
            if (const auto* fixed = llvm::dyn_cast<clang::ConstantArrayType>(raw))
            {
                const auto& size = fixed->getSize();
                if (size.getActiveBits() > 64)
                {
                    unsupported(owner, "Array extent exceeds the supported 64-bit range");
                    return { };
                }
                node.extent = size.getZExtValue();
            }
            else if (!llvm::isa<clang::IncompleteArrayType>(raw))
            {
                unsupported(owner, "Variable/dependent array extents are not supported");
                return { };
            }
            identity = "array:" + (node.extent ? std::to_string(*node.extent) : "incomplete") + ":" + node.childID;
        }
        else
        {
            unsupported(owner, "Unsupported structural type: " + node.spelling);
            return { };
        }
        if (facts.failed)
            return { };
        // Child/declaration identity components are fixed-size hashed IDs;
        // no type display spelling participates except the normalized builtin name.
        identity += ":cvr:" + std::to_string(node.isConst + 2 * node.isVolatile + 4 * node.isRestrict);
        node.id   = "type:" + digest(identity);
        interned.emplace(key, node.id);
        const auto canonical = context.getCanonicalType(value);
        node.canonicalID     = canonical == value ? node.id : get(canonical, owner);
        const auto id        = node.id;
        auto existing        = facts.types.find(id);
        if (existing == facts.types.end())
            facts.types.emplace(id, std::move(node));
        else if (node.spelling < existing->second.spelling)
            existing->second.spelling = node.spelling;
        return id;
    }

} // namespace trick::icg
