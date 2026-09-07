#pragma once

#include "Facts.hh"

#include "clang/AST/Decl.h"
#include "clang/Basic/SourceLocation.h"

#include <functional>

namespace clang
{
    class ASTContext;
}

namespace trick::icg
{
    struct DeclarationID
    {
            std::string id;
            std::string usr;
            bool fromSource = false;
    };

    // AST pointers are only memoization keys during this translation unit.
    // The emitted identity contains only USRs or rooted physical source anchors.
    class DeclarationIdentity
    {
            Facts& facts;
            clang::ASTContext& context;
            std::function<llvm::json::Value(clang::SourceLocation)> point;
            std::map<const clang::Decl*, DeclarationID> identities;
            std::map<std::string, const clang::Decl*> owners;
            std::map<unsigned, std::string> anchors;

            std::string anchor(clang::SourceLocation location);

        public:
            DeclarationIdentity(Facts& facts, clang::ASTContext& context,
                                std::function<llvm::json::Value(clang::SourceLocation)> point);
            const DeclarationID& get(const clang::NamedDecl* decl);
    };
}
