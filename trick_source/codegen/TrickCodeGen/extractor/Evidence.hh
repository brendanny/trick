#pragma once

#include "Facts.hh"

#include <optional>
#include <vector>

namespace trick::icg
{
    // Owned required declaration fields. Kind-specific builders add their facts
    // after this common header has been serialized; no borrowed AST data escapes.
    struct DeclarationHeader
    {
            std::string id, kind, name, qualifiedName, usr, access, origin;
            bool fromSource;
            llvm::json::Value source;
            llvm::json::Array annotations;

            llvm::json::Object json() const;
    };

    struct FriendSignature
    {
            std::string returnTypeUSR;
            std::vector<std::string> parameterTypeUSRs;
            bool returnsVoid, variadic, method;
            std::string languageLinkage;
            std::string exceptionSpec;
            bool isConst, isVolatile;
            std::string refQualifier;
            llvm::json::Object json() const;
    };

    // Targets can be outside the declaration graph. USRs are semantic target
    // evidence, not dangling declaration IDs or permission to access a member.
    struct FriendEvidence
    {
            std::string targetKind, targetUSR, targetQualifiedName;
            llvm::json::Value source;
            std::optional<FriendSignature> signature;
            llvm::json::Object json() const;
    };
}
