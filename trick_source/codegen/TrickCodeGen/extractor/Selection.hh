#pragma once

#include "Sources.hh"

#include "clang/AST/ASTContext.h"
#include "clang/AST/DeclTemplate.h"

#include <functional>

namespace trick::icg
{
    // Explicit physical-file requests only. Trick eligibility/exclusions are
    // policy and must not be inferred from named path roots here.
    class Selection
    {
            Facts& facts;
            Sources& sources;
            std::set<std::string> requestedPaths;
            std::set<std::string> selectedFiles;
            llvm::json::Array roots;
            std::set<std::string> occurrences;

        public:
            Selection(Facts& facts, Sources& sources, std::set<std::string> paths)
                : facts(facts)
                , sources(sources)
                , requestedPaths(std::move(paths))
            {
            }

            void run(clang::ASTContext& context, const std::function<std::string(const clang::NamedDecl*)>& request,
                     const std::function<void(const clang::Decl*, const std::string&)>& unsupported);
    };
}
