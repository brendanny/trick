#include "Sources.hh"

namespace trick::icg
{
    bool Comments::HandleComment(clang::Preprocessor& pp, clang::SourceRange range)
    {
        auto& sm         = pp.getSourceManager();
        const auto begin = sm.getSpellingLoc(range.getBegin());
        if (begin.isInvalid() || !sm.getFileEntryRefForID(sm.getFileID(begin)))
            return false; // Only physical input comments are evidence.
        const auto id = sources.file(sm, sm.getFileID(begin));
        if (id.empty() || !observed.emplace(id, sm.getFileOffset(begin)).second)
            return false;
        bool invalid         = false;
        size_t invalidOffset = 0;
        // The preprocessor's comment range is already character-delimited.
        // Do not extend it to the end of a following token.
        const auto text
            = clang::Lexer::getSourceText(clang::CharSourceRange::getCharRange(range), sm, pp.getLangOpts(), &invalid);
        auto location = sources.source(sm, range);
        if (invalid || location.kind() == llvm::json::Value::Null)
            facts.diagnose("error", "ICG_COMMENT_SOURCE", "Cannot recover physical comment bytes", std::move(location));
        else if (!llvm::json::isUTF8(text, &invalidOffset))
            facts.diagnose("error", "ICG_INVALID_ENCODING",
                           "Comment is not valid UTF-8 at byte offset " + std::to_string(invalidOffset),
                           std::move(location));
        else
        {
            auto& comments = *facts.files.at(id).getArray("comments");
            comments.emplace_back(llvm::json::Object {
                { "payload", text.str()          },
                { "source",  std::move(location) }
            });
        }
        return false;
    }

    std::string realPath(llvm::StringRef path)
    {
        llvm::SmallString<256> result;
        if (llvm::sys::fs::real_path(path, result))
            return { };
        return result.str().str();
    }

    std::string Sources::file(clang::SourceManager& sm, clang::FileID fid)
    {
        const auto entry = sm.getFileEntryRefForID(fid);
        if (!entry)
            return { }; // built-in/command-line buffers have no physical file
        std::string spelled = entry->getName().str();
        std::string real    = realPath(spelled);
        if (real.empty())
            real = spelled;
        std::string portable;
        std::string rootName;
        size_t matched = 0;
        for (const auto& root : roots)
        {
            const auto prefix = root.second.back() == '/' ? root.second : root.second + "/";
            if (prefix.size() > matched && llvm::StringRef(real).starts_with(prefix))
            {
                rootName = root.first;
                portable = real.substr(prefix.size());
                matched  = prefix.size();
            }
        }
        if (rootName.empty())
        {
            if (unmapped.insert(real).second)
                facts.diagnose("error", "ICG_UNMAPPED_FILE",
                               "No named path root contains " + spelled + "; configure --path-root NAME=DIR");
            return { };
        }
        std::string id = "file:" + digest(rootName + ":" + portable);
        if (!facts.files.count(id))
        {
            bool invalid  = false;
            auto contents = sm.getBufferData(fid, &invalid);
            if (invalid)
                facts.diagnose("error", "ICG_INPUT_READ", "Cannot read " + spelled);
            facts.files.emplace(
                id,
                Object {
                    { "id",             id                                                                           },
                    { "path",
                     Object {
                          { "spelled", spelled }, { "real", real }, { "root", rootName }, { "portable", portable } } },
                    { "classification", sm.isInSystemHeader(sm.getLocForStartOfFile(fid)) ? "system" : "user"        },
                    { "digest",         digest(contents)                                                             },
                    { "comments",       Array { }                                                                    },
                    { "includes",       Array { }                                                                    }
            });
        }
        return id;
    }
    Value Sources::point(clang::SourceManager& sm, clang::SourceLocation loc)
    {
        if (loc.isInvalid() || !loc.isFileID())
            return nullptr;
        auto id = file(sm, sm.getFileID(loc));
        if (id.empty())
            return nullptr;
        return Object {
            { "file_id", id                              },
            { "line",    sm.getSpellingLineNumber(loc)   },
            { "column",  sm.getSpellingColumnNumber(loc) },
            { "offset",  sm.getFileOffset(loc)           }
        };
    }
    Value Sources::source(clang::SourceManager& sm, clang::SourceRange range, const clang::LangOptions* lang)
    {
        if (range.isInvalid())
            return nullptr;
        auto begin = range.getBegin();
        auto end   = sm.getExpansionLoc(range.getEnd());
        if (lang)
        {
            auto after = clang::Lexer::getLocForEndOfToken(end, 0, sm, *lang);
            if (after.isValid())
                end = after;
        }
        auto spelling  = point(sm, sm.getSpellingLoc(begin));
        auto expansion = point(sm, sm.getExpansionLoc(begin));
        auto finish    = point(sm, end);
        if (spelling.kind() == Value::Null || expansion.kind() == Value::Null || finish.kind() == Value::Null)
            return nullptr;
        return Object {
            { "spelling",        std::move(spelling)  },
            { "expansion",       std::move(expansion) },
            { "end",             std::move(finish)    },
            { "macro_expansion", begin.isMacroID()    }
        };
    }
}
