#include "Config.hh"
#include "Facts.hh"

#include "clang/AST/ASTConsumer.h"
#include "clang/AST/ASTContext.h"
#include "clang/AST/Attr.h"
#include "clang/AST/DeclCXX.h"
#include "clang/AST/RecordLayout.h"
#include "clang/Basic/Diagnostic.h"
#include "clang/Basic/SourceManager.h"
#include "clang/Basic/TargetInfo.h"
#include "clang/Basic/Version.h"
#include "clang/Frontend/CompilerInstance.h"
#include "clang/Frontend/FrontendActions.h"
#include "clang/Index/USRGeneration.h"
#include "clang/Lex/Lexer.h"
#include "clang/Lex/PPCallbacks.h"
#include "clang/Lex/Preprocessor.h"
#include "clang/Tooling/CompilationDatabase.h"
#include "clang/Tooling/Tooling.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/Support/Path.h"

#include <cstdlib>
#include <memory>
#include <set>

namespace
{
    using llvm::json::Array;
    using llvm::json::Object;
    using llvm::json::Value;
    using trick::icg::digest;
    using trick::icg::Facts;
    using trick::icg::serialize;

    std::string realPath(llvm::StringRef path)
    {
        llvm::SmallString<256> result;
        if (llvm::sys::fs::real_path(path, result))
            return { };
        return result.str().str();
    }

    class Sources
    {
            Facts& facts;
            std::string root;

        public:
            Sources(Facts& facts, std::string root)
                : facts(facts)
                , root(std::move(root))
            {
            }

            std::string file(clang::SourceManager& sm, clang::FileID fid)
            {
                const auto* entry = sm.getFileEntryForID(fid);
                if (!entry)
                    return { }; // built-in/command-line buffers have no physical file
                std::string spelled = entry->getName().str();
                std::string real    = realPath(spelled);
                if (real.empty())
                    real = spelled;
                std::string portable = real;
                std::string prefix   = root.back() == '/' ? root : root + "/";
                if (llvm::StringRef(real).starts_with(prefix))
                    portable = real.substr(prefix.size());
                std::string id = "file:" + digest(portable);
                if (!facts.files.count(id))
                {
                    bool invalid  = false;
                    auto contents = sm.getBufferData(fid, &invalid);
                    if (invalid)
                        facts.diagnose("error", "ICG_INPUT_READ", "Cannot read " + spelled);
                    facts.files.emplace(
                        id,
                        Object {
                            { "id",             id                                                                            },
                            { "path",           Object { { "spelled", spelled }, { "real", real }, { "portable", portable } } },
                            { "classification", sm.isInSystemHeader(sm.getLocForStartOfFile(fid)) ? "system" : "user"         },
                            { "digest",         digest(contents)                                                              },
                            { "includes",       Array { }                                                                     }
                    });
                }
                return id;
            }

            Value point(clang::SourceManager& sm, clang::SourceLocation loc)
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

            Value source(clang::SourceManager& sm, clang::SourceRange range, const clang::LangOptions* lang = nullptr)
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
    };

    class Diagnostics : public clang::DiagnosticConsumer
    {
            Facts& facts;
            Sources& sources;

        public:
            Diagnostics(Facts& facts, Sources& sources)
                : facts(facts)
                , sources(sources)
            {
            }
            void HandleDiagnostic(clang::DiagnosticsEngine::Level level, const clang::Diagnostic& info) override
            {
                clang::DiagnosticConsumer::HandleDiagnostic(level, info);
                if (level == clang::DiagnosticsEngine::Ignored)
                    return;
                const char* severity = "error";
                switch (level)
                {
                case clang::DiagnosticsEngine::Note:
                    severity = "note";
                    break;
                case clang::DiagnosticsEngine::Remark:
                    severity = "note";
                    break;
                case clang::DiagnosticsEngine::Warning:
                    severity = "warning";
                    break;
                case clang::DiagnosticsEngine::Fatal:
                    severity = "fatal";
                    break;
                default:
                    break;
                }
                llvm::SmallString<256> message;
                info.FormatDiagnostic(message);
                Value source = nullptr;
                if (info.hasSourceManager())
                    source = sources.source(info.getSourceManager(), clang::SourceRange(info.getLocation()));
                facts.diagnose(severity, "CLANG_" + std::to_string(info.getID()), message.str().str(),
                               std::move(source));
            }
    };

    class Includes : public clang::PPCallbacks
    {
            Facts& facts;
            Sources& sources;
            clang::SourceManager& sm;
            const clang::LangOptions& lang;

        public:
            Includes(Facts& facts, Sources& sources, clang::CompilerInstance& ci)
                : facts(facts)
                , sources(sources)
                , sm(ci.getSourceManager())
                , lang(ci.getLangOpts())
            {
            }

            void LexedFileChanged(clang::FileID fid, LexedFileChangeReason reason, clang::SrcMgr::CharacteristicKind,
                                  clang::FileID, clang::SourceLocation) override
            {
                if (reason == LexedFileChangeReason::EnterFile)
                    sources.file(sm, fid);
            }

            void InclusionDirective(clang::SourceLocation hash, const clang::Token&, llvm::StringRef name, bool angled,
                                    clang::CharSourceRange range, clang::OptionalFileEntryRef entry, llvm::StringRef,
                                    llvm::StringRef, const clang::Module*,
                                    clang::SrcMgr::CharacteristicKind kind) override
            {
                if (!entry)
                    return; // Clang reports missing includes separately.
                auto fid = sm.translateFile(*entry);
                if (fid.isInvalid())
                    fid = sm.createFileID(*entry, hash, kind);
                auto target   = sources.file(sm, fid);
                auto owner    = sources.file(sm, sm.getFileID(sm.getExpansionLoc(hash)));
                auto location = sources.source(sm, clang::SourceRange(hash, range.getEnd()), &lang);
                if (!owner.empty() && !target.empty() && location.kind() != Value::Null)
                {
                    facts.files.at(owner)
                        .getArray("includes")
                        ->emplace_back(Object {
                            { "file_id",  target              },
                            { "spelling", name.str()          },
                            { "angled",   angled              },
                            { "source",   std::move(location) }
                    });
                }
            }
    };

    std::string usr(const clang::Decl* decl)
    {
        llvm::SmallString<128> result;
        if (clang::index::generateUSRForDecl(decl, result))
            return { };
        return result.str().str();
    }

    std::string declarationID(const clang::Decl* decl) { return "decl:" + digest(usr(decl)); }

    const char* access(clang::AccessSpecifier value)
    {
        switch (value)
        {
        case clang::AS_public:
            return "public";
        case clang::AS_protected:
            return "protected";
        case clang::AS_private:
            return "private";
        case clang::AS_none:
            return "none";
        }
        return "none";
    }

    class Consumer : public clang::ASTConsumer
    {
            Facts& facts;
            Sources& sources;

            void unsupported(clang::ASTContext& ctx, const clang::Decl* decl, const std::string& message)
            {
                facts.diagnose("error", "ICG_UNSUPPORTED_DECLARATION", message,
                               sources.source(ctx.getSourceManager(), decl->getSourceRange(), &ctx.getLangOpts()));
            }

            Object common(clang::ASTContext& ctx, const clang::NamedDecl* decl, const char* kind)
            {
                auto location = sources.source(ctx.getSourceManager(), decl->getSourceRange(), &ctx.getLangOpts());
                if (location.kind() == Value::Null || usr(decl).empty())
                    unsupported(ctx, decl, "Declaration has no supported physical source or stable USR");
                Array annotations;
                if (const auto* comment = ctx.getRawCommentForDeclNoCache(decl))
                {
                    annotations.emplace_back(Object {
                        { "syntax", "comment" },
                        { "payload", comment->getRawText(ctx.getSourceManager()).str() },
                        { "source",
                         sources.source(ctx.getSourceManager(), comment->getSourceRange(), &ctx.getLangOpts()) }
                    });
                }
                for (const auto* attribute : decl->specific_attrs<clang::AnnotateAttr>())
                {
                    annotations.emplace_back(Object {
                        { "syntax", "clang-annotate" },
                        { "payload", attribute->getAnnotation().str() },
                        { "source",
                         sources.source(ctx.getSourceManager(), attribute->getRange(), &ctx.getLangOpts()) }
                    });
                }
                for (const auto& annotation : annotations)
                    if (annotation.getAsObject()->get("source")->kind() == Value::Null)
                        unsupported(ctx, decl, "Annotation has no supported physical source location");
                return Object {
                    { "id",                       declarationID(decl)              },
                    { "kind",                     kind                             },
                    { "name",                     decl->getNameAsString()          },
                    { "qualified_name",           decl->getQualifiedNameAsString() },
                    { "usr",                      usr(decl)                        },
                    { "source",                   std::move(location)              },
                    { "access",                   access(decl->getAccess())        },
                    { "origin",                   "user"                           },
                    { "definition",               true                             },
                    { "canonical_declaration_id", declarationID(decl)              },
                    { "annotations",              std::move(annotations)           },
                    { "capabilities",             Array { }                        }
                };
            }

            std::string type(clang::QualType value, const clang::CXXRecordDecl* record = nullptr)
            {
                auto spelling = value.getAsString();
                auto id       = "type:" + digest(record ? "record:" + usr(record) : "builtin:" + spelling);
                Object node {
                    { "id",           id                                     },
                    { "kind",         record ? "record" : "builtin"          },
                    { "spelling",     spelling                               },
                    { "canonical_id", id                                     },
                    { "qualifiers",
                     Object { { "const", value.isConstQualified() },
                               { "volatile", value.isVolatileQualified() },
                               { "restrict", value.isRestrictQualified() } } }
                };
                if (record)
                    node["declaration_id"] = declarationID(record);
                facts.types.emplace(id, std::move(node));
                return id;
            }

            void record(clang::ASTContext& ctx, const clang::CXXRecordDecl* decl)
            {
                if (!decl->isCompleteDefinition() || decl->getIdentifier() == nullptr || decl->isDependentType()
                    || decl->getNumBases() != 0 || decl->getDescribedClassTemplate()
                    || llvm::isa<clang::ClassTemplateSpecializationDecl>(decl))
                {
                    unsupported(ctx, decl, "Only complete named non-template records without bases are supported");
                    return;
                }
                for (const auto* member : decl->decls())
                {
                    if (member->isImplicit() || llvm::isa<clang::AccessSpecDecl>(member))
                        continue;
                    const auto* field = llvm::dyn_cast<clang::FieldDecl>(member);
                    if (!field || field->getIdentifier() == nullptr || field->isBitField()
                        || !llvm::isa<clang::BuiltinType>(field->getType().getTypePtr()))
                    {
                        unsupported(ctx, member, "Only named non-bitfield builtin data members are supported");
                        return;
                    }
                }
                const auto& layout             = ctx.getASTRecordLayout(decl);
                auto node                      = common(ctx, decl, "record");
                node["type_id"]                = type(ctx.getRecordType(decl), decl);
                node["record_tag"]             = decl->isUnion() ? "union" : (decl->isClass() ? "class" : "struct");
                node["complete"]               = true;
                node["abstract"]               = decl->isAbstract();
                node["pod"]                    = decl->isPOD();
                node["standard_layout"]        = decl->isStandardLayout();
                node["trivial"]                = decl->isTrivial();
                node["size_bits"]              = layout.getSize().getQuantity() * ctx.getCharWidth();
                node["alignment_bits"]         = layout.getAlignment().getQuantity() * ctx.getCharWidth();
                node["bases"]                  = Array { };
                node["nested_declaration_ids"] = Array { };
                node["capabilities"]           = Array {
                    Object { { "name", "frontend-record-layout" },
                            { "status", "supported" },
                            { "reason_code", "SUPPORTED" } }
                };
                Array fields;
                unsigned index = 0;
                for (const auto* field : decl->fields())
                {
                    auto data                  = common(ctx, field, "field");
                    data["semantic_parent_id"] = declarationID(decl);
                    data["lexical_parent_id"]  = declarationID(decl);
                    data["type_id"]            = type(field->getType());
                    data["static"]             = false;
                    data["mutable"]            = field->isMutable();
                    data["bitfield"]           = false;
                    data["bit_width"]          = nullptr;
                    data["offset_bits"]        = layout.getFieldOffset(index++);
                    fields.emplace_back(declarationID(field));
                    facts.declarations.emplace(declarationID(field), std::move(data));
                }
                node["field_ids"] = std::move(fields);
                facts.declarations.emplace(declarationID(decl), std::move(node));
            }

        public:
            Consumer(Facts& facts, Sources& sources)
                : facts(facts)
                , sources(sources)
            {
            }
            void HandleTranslationUnit(clang::ASTContext& ctx) override
            {
                if (ctx.getDiagnostics().hasErrorOccurred())
                    return;
                auto& sm                             = ctx.getSourceManager();
                facts.provenance["translation_unit"] = sources.file(sm, sm.getMainFileID());
                facts.provenance["target_triple"]    = ctx.getTargetInfo().getTriple().str();
                for (const auto* decl : ctx.getTranslationUnitDecl()->decls())
                {
                    if (decl->isImplicit() || !sm.isWrittenInMainFile(sm.getExpansionLoc(decl->getLocation())))
                        continue;
                    if (const auto* value = llvm::dyn_cast<clang::CXXRecordDecl>(decl))
                        record(ctx, value);
                    else if (!llvm::isa<clang::EmptyDecl, clang::StaticAssertDecl>(decl))
                        unsupported(ctx, decl, "Only top-level records are extracted in this initial slice");
                }
            }
    };

    class Action : public clang::ASTFrontendAction
    {
            Facts& facts;
            Sources& sources;

        public:
            Action(Facts& facts, Sources& sources)
                : facts(facts)
                , sources(sources)
            {
            }
            std::unique_ptr<clang::ASTConsumer> CreateASTConsumer(clang::CompilerInstance& ci, llvm::StringRef) override
            {
                ci.getPreprocessor().addPPCallbacks(std::make_unique<Includes>(facts, sources, ci));
                return std::make_unique<Consumer>(facts, sources);
            }
    };

    class Factory : public clang::tooling::FrontendActionFactory
    {
            Facts& facts;
            Sources& sources;

        public:
            Factory(Facts& facts, Sources& sources)
                : facts(facts)
                , sources(sources)
            {
            }
            std::unique_ptr<clang::FrontendAction> create() override
            {
                return std::make_unique<Action>(facts, sources);
            }
    };

    // This is an intentionally small Clang-argument interface, not the future GCC
    // command normalizer. Reject everything not audited here; never silently strip
    // code-generation flags or accept plugins/response files with hidden arguments.
    bool checkArguments(const std::vector<std::string>& args, Facts& facts)
    {
        const std::set<std::string> paired { "-I",       "-isystem",  "-iquote",   "-D",      "-U",      "-include",
                                             "-imacros", "--sysroot", "-isysroot", "-target", "--target" };
        for (size_t i = 0; i < args.size(); ++i)
        {
            llvm::StringRef arg(args[i]);
            if (paired.count(args[i]))
            {
                if (++i < args.size() && !args[i].empty())
                    continue;
                facts.diagnose("error", "ICG_ARGUMENT_VALUE", "Missing value for " + arg.str());
                return false;
            }
            if (arg == "-std=c++17" || arg == "-m32" || arg == "-m64" || arg == "-fno-exceptions" || arg == "-fno-rtti"
                || (arg.starts_with("-W") && arg.size() > 2 && !arg.starts_with("-Wl,") && !arg.starts_with("-Wa,")
                    && !arg.starts_with("-Wp,"))
                || ((arg.starts_with("-I") || arg.starts_with("-D") || arg.starts_with("-U")) && arg.size() > 2)
                || arg.starts_with("--target=") || arg.starts_with("--sysroot="))
                continue;
            facts.diagnose("error", "ICG_UNSUPPORTED_ARGUMENT", "Unsupported compiler argument: " + arg.str());
            return false;
        }
        return true;
    }

    void printDiagnostics(const Facts& facts, bool json)
    {
        if (json)
        {
            Array files;
            for (const auto& entry : facts.files)
                files.emplace_back(Object(entry.second));
            llvm::errs() << serialize(Object {
                { "schema_version", 1                        },
                { "document_kind",  "trick.icg.diagnostics"  },
                { "files",          std::move(files)         },
                { "diagnostics",    Array(facts.diagnostics) }
            })
                         << '\n';
        }
        else
        {
            for (const auto& value : facts.diagnostics)
            {
                const auto& entry = *value.getAsObject();
                if (const auto* source = entry.getObject("source"))
                {
                    const auto* point = source->getObject("expansion");
                    const auto& file  = facts.files.at(point->getString("file_id")->str());
                    llvm::errs() << *file.getObject("path")->getString("spelled") << ':' << *point->getInteger("line")
                                 << ':' << *point->getInteger("column") << ": ";
                }
                llvm::errs() << *entry.getString("severity") << " [" << *entry.getString("code")
                             << "]: " << *entry.getString("message") << '\n';
            }
        }
    }
} // namespace

int main(int argc, const char** argv)
{
    Facts facts;
    std::string input;
    llvm::SmallString<256> cwd;
    if (llvm::sys::fs::current_path(cwd))
        return 2;
    std::string root     = cwd.str().str();
    bool jsonDiagnostics = false;
    bool separator       = false;
    std::vector<std::string> arguments;
    for (int i = 1; i < argc; ++i)
    {
        std::string arg(argv[i]);
        if (separator)
            arguments.push_back(arg);
        else if (arg == "--")
            separator = true;
        else if (arg == "--diagnostics-format=json")
            jsonDiagnostics = true;
        else if (arg == "--source-root" && i + 1 < argc)
            root = argv[++i];
        else if (arg == "--help")
        {
            llvm::outs()
                << "Usage: trick-icg-extract [--source-root DIR] [--diagnostics-format=json] HEADER -- [CLANG FLAGS]\n"
                   "C++17, one input, stdout facts; diagnostics on stderr. See TrickCodeGen/README.md.\n";
            return 0;
        }
        else if (!arg.empty() && arg[0] != '-' && input.empty())
            input = arg;
        else
            facts.diagnose("error", "ICG_USAGE", "Unexpected extractor argument: " + arg);
    }
    if (input.empty() || !separator)
        facts.diagnose("error", "ICG_USAGE", "Provide one input and an explicit -- separator");
    root = realPath(root);
    if (root.empty() || !llvm::sys::fs::is_directory(root))
        facts.diagnose("error", "ICG_SOURCE_ROOT", "Source root must be an existing directory");
    if (!input.empty() && realPath(input).empty())
        facts.diagnose("error", "ICG_INPUT_READ", "Cannot resolve input: " + input);
    checkArguments(arguments, facts);
    if (facts.failed)
    {
        printDiagnostics(facts, jsonDiagnostics);
        return 2;
    }

    Sources sources(facts, root);
    Diagnostics diagnostics(facts, sources);
    Factory factory(facts, sources);
    std::vector<std::string> flags { "-x",
                                     "c++",
                                     "-std=c++17",
                                     "-resource-dir",
                                     ICG_RESOURCE_DIR,
                                     "-fparse-all-comments",
                                     "-fsyntax-only",
                                     "-fno-caret-diagnostics",
                                     "-Werror=unknown-warning-option" };
    flags.insert(flags.end(), arguments.begin(), arguments.end());
    clang::tooling::FixedCompilationDatabase database(cwd, flags);
    clang::tooling::ClangTool tool(database, { input });
    tool.setDiagnosticConsumer(&diagnostics);
    tool.setPrintErrorMessage(false);
    tool.clearArgumentsAdjusters();
    tool.appendArgumentsAdjuster(
        [&facts](const clang::tooling::CommandLineArguments& args, llvm::StringRef)
        {
            auto adjusted = args;
            adjusted[0]   = ICG_CLANG_EXECUTABLE;
            Array recorded;
            for (const auto& arg : adjusted)
                recorded.emplace_back(arg);
            facts.provenance["arguments"] = std::move(recorded);
            return adjusted;
        });
    Object environment;
    for (const auto* name : { "CPATH", "CPLUS_INCLUDE_PATH", "C_INCLUDE_PATH", "SDKROOT", "MACOSX_DEPLOYMENT_TARGET",
                              "SOURCE_DATE_EPOCH" })
        if (const auto* value = std::getenv(name))
            environment[name] = std::string(value);
    facts.provenance["extractor_version"] = ICG_EXTRACTOR_VERSION;
    facts.provenance["frontend_api"]      = "libtooling";
    facts.provenance["frontend_version"]  = clang::getClangFullVersion();
    facts.provenance["language_standard"] = "c++17";
    facts.provenance["working_directory"] = cwd.str().str();
    facts.provenance["environment"]       = std::move(environment);
    int result                            = tool.run(&factory);
    if (result && !facts.failed)
        facts.diagnose("error", "ICG_FRONTEND_FAILED", "Clang invocation did not complete");
    if (!facts.failed && !facts.provenance.getString("translation_unit"))
        facts.diagnose("error", "ICG_NO_TRANSLATION_UNIT", "No translation unit was extracted");
    printDiagnostics(facts, jsonDiagnostics);
    if (facts.failed)
        return 1;
    // Evidence fingerprint, NOT a production cache key: exact arguments, paths,
    // environment, frontend facts, and contents of observed physical inputs.
    facts.provenance["input_digest"] = digest(serialize(facts.document()));
    llvm::outs() << serialize(facts.document()) << '\n';
    return 0;
}
