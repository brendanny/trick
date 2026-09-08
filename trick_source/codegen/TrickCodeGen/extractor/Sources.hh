#pragma once

#include "Facts.hh"

#include "clang/Basic/SourceManager.h"
#include "clang/Lex/Lexer.h"
#include "clang/Lex/Preprocessor.h"
#include "llvm/Support/FileSystem.h"

#include <set>

namespace trick::icg
{
    std::string realPath(llvm::StringRef path);
    using llvm::json::Array;
    using llvm::json::Object;
    using llvm::json::Value;

    class Sources
    {
            Facts& facts;
            std::map<std::string, std::string> roots;
            std::set<std::string> unmapped;

        public:
            Sources(Facts& facts, std::map<std::string, std::string> roots)
                : facts(facts)
                , roots(std::move(roots))
            {
            }

            std::string file(clang::SourceManager& sm, clang::FileID fid);

            Value point(clang::SourceManager& sm, clang::SourceLocation loc);

            Value source(clang::SourceManager& sm, clang::SourceRange range, const clang::LangOptions* lang = nullptr);
    };
    class Comments : public clang::CommentHandler
    {
            Facts& facts;
            Sources& sources;
            std::set<std::pair<std::string, unsigned>> observed;

        public:
            Comments(Facts& facts, Sources& sources)
                : facts(facts)
                , sources(sources)
            {
            }
            bool HandleComment(clang::Preprocessor& pp, clang::SourceRange range) override;
    };
}
