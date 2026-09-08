#pragma once

#include "Facts.hh"

#include "clang/AST/ASTContext.h"

#include <functional>
#include <map>

namespace clang
{
    class Sema;
}

namespace trick::icg
{

    // A translation-unit-local adapter. requestDeclaration queues closure work; it
    // must not recursively extract record fields while a type is being interned.
    class TypeGraph
    {
            Facts& facts;
            clang::ASTContext& context;
            clang::Sema& sema;
            std::function<std::string(const clang::NamedDecl*)> requestDeclaration;
            std::function<void(const clang::Decl*, const std::string&)> unsupported;
            // Clang may share pattern typedef sugar across concrete instances.
            // Memoize within the use's context; structural IDs still intern
            // equivalent resolved nodes across contexts.
            std::map<std::pair<const void*, const clang::Decl*>, std::string> interned;

        public:
            TypeGraph(Facts& facts, clang::ASTContext& context, clang::Sema& sema,
                      std::function<std::string(const clang::NamedDecl*)> requestDeclaration,
                      std::function<void(const clang::Decl*, const std::string&)> unsupported);
            std::string get(clang::QualType type, const clang::Decl* owner);
    };

} // namespace trick::icg
