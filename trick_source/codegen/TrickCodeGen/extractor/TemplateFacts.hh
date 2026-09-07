#pragma once

#include "TypeGraph.hh"

#include "clang/AST/DeclTemplate.h"

namespace trick::icg
{
    // Template patterns have source/signature evidence, not instantiated layout.
    // Concrete arguments are read from Clang's semantic list, including packs.
    class TemplateFacts
    {
            clang::ASTContext& context;
            TypeGraph& types;
            std::function<std::string(const clang::NamedDecl*)> request;
            std::function<llvm::json::Value(clang::SourceRange)> source;
            std::function<void(const clang::Decl*, const std::string&)> unsupported;

            llvm::json::Value argument(const clang::TemplateArgument& value, const clang::Decl* owner);

        public:
            TemplateFacts(clang::ASTContext& context, TypeGraph& types,
                          std::function<std::string(const clang::NamedDecl*)> request,
                          std::function<llvm::json::Value(clang::SourceRange)> source,
                          std::function<void(const clang::Decl*, const std::string&)> unsupported);
            llvm::json::Array arguments(const clang::TemplateArgumentList& values, const clang::Decl* owner);
            llvm::json::Array parameters(const clang::TemplateParameterList* values);
    };
}
