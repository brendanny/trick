#pragma once

#include "Facts.hh"

#include "clang/AST/ASTContext.h"

#include <functional>
#include <map>

namespace trick::icg
{

    // A translation-unit-local adapter. requestDeclaration queues closure work; it
    // must not recursively extract record fields while a type is being interned.
    class TypeGraph
    {
            Facts& facts;
            clang::ASTContext& context;
            std::function<std::string(const clang::NamedDecl*)> requestDeclaration;
            std::function<void(const clang::Decl*, const std::string&)> unsupported;
            std::map<const void*, std::string> interned;

        public:
            TypeGraph(Facts& facts, clang::ASTContext& context,
                      std::function<std::string(const clang::NamedDecl*)> requestDeclaration,
                      std::function<void(const clang::Decl*, const std::string&)> unsupported);
            std::string get(clang::QualType type, const clang::Decl* owner);
    };

} // namespace trick::icg
