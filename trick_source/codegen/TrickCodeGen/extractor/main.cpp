#include "ClangCompat.hh"
#include "Config.hh"
#include "DeclarationIdentity.hh"
#include "Facts.hh"
#include "TemplateFacts.hh"
#include "TypeGraph.hh"

#include "clang/AST/ASTConsumer.h"
#include "clang/AST/ASTContext.h"
#include "clang/AST/Attr.h"
#include "clang/AST/DeclCXX.h"
#include "clang/AST/DeclFriend.h"
#include "clang/AST/RecordLayout.h"
#include "clang/Basic/Diagnostic.h"
#include "clang/Basic/SourceManager.h"
#include "clang/Basic/TargetInfo.h"
#include "clang/Basic/Version.h"
#include "clang/Frontend/CompilerInstance.h"
#include "clang/Frontend/FrontendActions.h"
#include "clang/Lex/Lexer.h"
#include "clang/Lex/PPCallbacks.h"
#include "clang/Lex/Preprocessor.h"
#include "clang/Sema/Sema.h"
#include "clang/Tooling/CompilationDatabase.h"
#include "clang/Tooling/Tooling.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/Support/Path.h"

#include <algorithm>
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

    std::string qualifiedDisplayName(const clang::NamedDecl* decl, const clang::PrintingPolicy& policy)
    {
        std::string name;
        if (!decl->getDeclName().isEmpty())
        {
            llvm::raw_string_ostream out(name);
            // Preserve constructors, operators, and conversion names under the
            // same printing policy without asking Clang to print their context.
            decl->getDeclName().print(out, policy);
            if (const auto* specialization = llvm::dyn_cast<clang::ClassTemplateSpecializationDecl>(decl))
            {
                if (const auto* partial = llvm::dyn_cast<clang::ClassTemplatePartialSpecializationDecl>(decl))
                    clang::printTemplateArgumentList(out, partial->getTemplateArgsAsWritten()->arguments(), policy);
                else
                    clang::printTemplateArgumentList(out, specialization->getTemplateArgs().asArray(), policy);
            }
        }
        else if (llvm::isa<clang::NamespaceDecl>(decl))
            name = "(anonymous namespace)";
        else if (const auto* tag = llvm::dyn_cast<clang::TagDecl>(decl))
        {
            if (const auto* alias = tag->getTypedefNameForAnonDecl())
                name = alias->getNameAsString();
            else
                name = "(anonymous " + tag->getKindName().str() + ")";
        }
        else if (const auto* field = llvm::dyn_cast<clang::FieldDecl>(decl))
            name = field->isAnonymousStructOrUnion() ? "(anonymous member)" : "(unnamed bitfield)";

        const auto* context = decl->getDeclContext();
        while (!context->isTranslationUnit())
        {
            const auto* contextDecl = clang::Decl::castFromDeclContext(context);
            const auto* linkage     = llvm::dyn_cast<clang::LinkageSpecDecl>(contextDecl);
            if (!linkage)
                break;
            context = linkage->getDeclContext();
        }
        if (!context->isTranslationUnit())
            if (const auto* parent = llvm::dyn_cast<clang::NamedDecl>(clang::Decl::castFromDeclContext(context)))
            {
                auto prefix = qualifiedDisplayName(parent, policy);
                if (!prefix.empty())
                    name = prefix + "::" + name;
            }
        return name;
    }

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

            std::string file(clang::SourceManager& sm, clang::FileID fid)
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
                            { "id",             id                                                                    },
                            { "path",
                             Object { { "spelled", spelled },
                                       { "real", real },
                                       { "root", rootName },
                                       { "portable", portable } }                                                     },
                            { "classification", sm.isInSystemHeader(sm.getLocForStartOfFile(fid)) ? "system" : "user" },
                            { "digest",         digest(contents)                                                      },
                            { "includes",       Array { }                                                             }
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

    class Includes : public trick::icg::compat::PPCallbacks
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

            void inclusion(clang::SourceLocation hash, llvm::StringRef name, bool angled, clang::CharSourceRange range,
                           clang::OptionalFileEntryRef entry, clang::SrcMgr::CharacteristicKind kind) override
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
            clang::CompilerInstance& compiler;
            clang::ASTContext* context = nullptr;
            std::unique_ptr<trick::icg::TypeGraph> types;
            std::unique_ptr<trick::icg::DeclarationIdentity> identities;
            std::unique_ptr<trick::icg::TemplateFacts> templates;
            std::vector<const clang::NamedDecl*> pending;
            std::set<std::string> queued;

            std::string declarationID(const clang::NamedDecl* decl) { return identities->get(decl).id; }

            std::string parentID(const clang::DeclContext* parent)
            {
                if (parent->isTranslationUnit())
                    return { };
                const auto* decl = clang::Decl::castFromDeclContext(parent);
                // Language-linkage blocks are transparent declaration contexts.
                // Preserve the surrounding namespace/record as the IR parent.
                if (const auto* linkage = llvm::dyn_cast<clang::LinkageSpecDecl>(decl))
                    return parentID(linkage->getDeclContext());
                if (const auto* record = llvm::dyn_cast<clang::CXXRecordDecl>(decl);
                    record && record->isDependentType())
                {
                    unsupported(*context, decl, "Dependent record contexts require template-body modeling");
                    return { };
                }
                if (llvm::isa<clang::CXXRecordDecl, clang::NamespaceDecl>(decl))
                    return request(llvm::cast<clang::NamedDecl>(decl));
                unsupported(*context, decl, "Only namespace and record declaration contexts are supported");
                return { };
            }

            void unsupported(clang::ASTContext& ctx, const clang::Decl* decl, const std::string& message)
            {
                facts.diagnose("error", "ICG_UNSUPPORTED_DECLARATION", message,
                               sources.source(ctx.getSourceManager(), decl->getSourceRange(), &ctx.getLangOpts()));
            }

            std::string request(const clang::NamedDecl* decl)
            {
                if (!decl)
                {
                    facts.diagnose("error", "ICG_DECLARATION_REFERENCE", "Declaration reference has no target");
                    return { };
                }
                if (const auto* record = llvm::dyn_cast<clang::CXXRecordDecl>(decl))
                {
                    if (const auto* pattern = record->getDescribedClassTemplate())
                        return request(pattern);
                    decl = record->getDefinition() ? record->getDefinition() : record->getCanonicalDecl();
                }
                else if (const auto* pattern = llvm::dyn_cast<clang::ClassTemplateDecl>(decl))
                {
                    const auto* definition = pattern->getTemplatedDecl()->getDefinition();
                    decl = definition ? definition->getDescribedClassTemplate() : pattern->getMostRecentDecl();
                }
                else if (const auto* enumeration = llvm::dyn_cast<clang::EnumDecl>(decl))
                    decl
                        = enumeration->getDefinition() ? enumeration->getDefinition() : enumeration->getCanonicalDecl();
                else if (const auto* alias = llvm::dyn_cast<clang::TypedefNameDecl>(decl))
                    decl = alias->getCanonicalDecl();
                else if (const auto* ns = llvm::dyn_cast<clang::NamespaceDecl>(decl))
                    decl = ns->getCanonicalDecl();
                else if (llvm::isa<clang::NamespaceAliasDecl>(decl))
                    decl = llvm::cast<clang::NamedDecl>(decl->getCanonicalDecl());
                else if (const auto* function = llvm::dyn_cast<clang::FunctionDecl>(decl))
                    decl = function->getMostRecentDecl();
                else
                {
                    unsupported(*context, decl,
                                "Only records, enums, aliases, callables, and namespace references are supported");
                    return { };
                }
                auto id = declarationID(decl);
                if (id.empty())
                    return id;
                if (!queued.insert(id).second)
                    return id;
                for (const auto* parent : { decl->getDeclContext(), decl->getLexicalDeclContext() })
                {
                    parentID(parent);
                }
                pending.push_back(decl);
                return id;
            }

            void request(const clang::NamedDecl* decl, std::set<std::string>& ids)
            {
                auto id = request(decl);
                if (!id.empty())
                    ids.insert(std::move(id));
            }

            void publish(const clang::NamedDecl* decl, Object node)
            {
                auto id = declarationID(decl);
                if (!id.empty())
                    facts.declarations.emplace(std::move(id), std::move(node));
            }

            Array annotations(clang::ASTContext& ctx, const clang::NamedDecl* decl)
            {
                Array annotations;
                bool validComment   = false;
                const auto* comment = trick::icg::compat::localRawComment(ctx, decl, validComment);
                if (!validComment)
                    unsupported(ctx, decl, "Cannot recover occurrence-specific raw comment bytes");
                if (comment)
                {
                    const auto payload = comment->getRawText(ctx.getSourceManager());
                    auto location
                        = sources.source(ctx.getSourceManager(), comment->getSourceRange(), &ctx.getLangOpts());
                    size_t offset = 0;
                    if (!llvm::json::isUTF8(payload, &offset))
                        facts.diagnose("error", "ICG_INVALID_ENCODING",
                                       "Comment is not valid UTF-8 at byte offset " + std::to_string(offset),
                                       std::move(location));
                    else
                        annotations.emplace_back(Object {
                            { "syntax",  "comment"           },
                            { "payload", payload.str()       },
                            { "source",  std::move(location) }
                        });
                }
                for (const auto* attribute : decl->specific_attrs<clang::AnnotateAttr>())
                {
                    const auto payload = attribute->getAnnotation();
                    auto location = sources.source(ctx.getSourceManager(), attribute->getRange(), &ctx.getLangOpts());
                    size_t offset = 0;
                    if (!llvm::json::isUTF8(payload, &offset))
                        facts.diagnose("error", "ICG_INVALID_ENCODING",
                                       "Annotation is not valid UTF-8 at byte offset " + std::to_string(offset),
                                       std::move(location));
                    else
                        annotations.emplace_back(Object {
                            { "syntax",  "clang-annotate"    },
                            { "payload", payload.str()       },
                            { "source",  std::move(location) }
                        });
                }
                for (const auto& annotation : annotations)
                    if (annotation.getAsObject()->get("source")->kind() == Value::Null)
                        unsupported(ctx, decl, "Annotation has no supported physical source location");
                return annotations;
            }

            Object common(clang::ASTContext& ctx, const clang::NamedDecl* decl, const char* kind)
            {
                auto location = sources.source(ctx.getSourceManager(), decl->getSourceRange(), &ctx.getLangOpts());
                const auto& identity = identities->get(decl);
                if (location.kind() == Value::Null || identity.id.empty())
                    unsupported(ctx, decl, "Declaration has no supported physical source or stable identity");
                clang::PrintingPolicy policy(ctx.getLangOpts());
                trick::icg::compat::anonymousNamesWithoutLocations(policy);
                policy.SuppressInlineNamespace = false;
                Object node {
                    { "id", declarationID(decl) },
                    { "kind", kind },
                    { "name", decl->getNameAsString() },
                    { "qualified_name", qualifiedDisplayName(decl, policy) },
                    { "usr", identity.usr.empty() ? Value(nullptr) : Value(identity.usr) },
                    { "identity_kind", identity.fromSource ? "source" : "usr" },
                    { "source", std::move(location) },
                    { "access", access(decl->getAccess()) },
                    { "origin", ctx.getSourceManager().isInSystemHeader(decl->getLocation()) ? "system" : "user" },
                    { "definition", true },
                    { "canonical_declaration_id", declarationID(decl) },
                    { "annotations", annotations(ctx, decl) },
                    { "capabilities", Array { } }
                };
                auto semantic = parentID(decl->getDeclContext());
                auto lexical  = parentID(decl->getLexicalDeclContext());
                if (!semantic.empty())
                    node["semantic_parent_id"] = semantic;
                if (!lexical.empty())
                    node["lexical_parent_id"] = lexical;
                return node;
            }

            void namespaceDecl(clang::ASTContext& ctx, const clang::NamespaceDecl* decl)
            {
                auto node               = common(ctx, decl, "namespace");
                node["anonymous"]       = decl->isAnonymousNamespace();
                node["inline"]          = decl->isInline();
                node["declaration_ids"] = Array { };
                std::vector<const clang::NamespaceDecl*> blocks(decl->redecls_begin(), decl->redecls_end());
                auto& sm = ctx.getSourceManager();
                std::sort(blocks.begin(), blocks.end(), [&sm](const auto* a, const auto* b)
                          { return sm.isBeforeInTranslationUnit(a->getBeginLoc(), b->getBeginLoc()); });
                Array locations;
                Array annotations;
                for (const auto* block : blocks)
                {
                    auto occurrence = common(ctx, block, "namespace");
                    locations.emplace_back(std::move(*occurrence.get("source")));
                    for (auto& annotation : *occurrence.getArray("annotations"))
                        annotations.emplace_back(std::move(annotation));
                }
                node["reopening_sources"] = std::move(locations);
                node["annotations"]       = std::move(annotations);
                publish(decl, std::move(node));
            }

            void namespaceAlias(clang::ASTContext& ctx, const clang::NamespaceAliasDecl* decl)
            {
                auto node   = common(ctx, decl, "namespace_alias");
                auto target = request(decl->getAliasedNamespace());
                if (target.empty())
                    return;
                node["target_namespace_id"] = std::move(target);
                publish(decl, std::move(node));
            }

            void selectMainFile(clang::ASTContext& ctx, const clang::DeclContext* scope)
            {
                auto& sm = ctx.getSourceManager();
                for (const auto* decl : scope->decls())
                {
                    if (decl->isImplicit())
                        continue;
                    if (const auto* ns = llvm::dyn_cast<clang::NamespaceDecl>(decl))
                        selectMainFile(ctx, ns);
                    if (const auto* linkage = llvm::dyn_cast<clang::LinkageSpecDecl>(decl))
                    {
                        selectMainFile(ctx, linkage);
                        continue;
                    }
                    // Explicit instantiation directives may live only in the
                    // primary template's specialization set, not scope->decls().
                    // The primary itself may come from an included header.
                    if (const auto* pattern = llvm::dyn_cast<clang::ClassTemplateDecl>(decl))
                        for (const auto* instance : pattern->specializations())
                            if (clang::isTemplateExplicitInstantiationOrSpecialization(
                                    instance->getSpecializationKind())
                                && sm.isWrittenInMainFile(sm.getExpansionLoc(instance->getPointOfInstantiation())))
                                request(instance);
                    if (!sm.isWrittenInMainFile(sm.getExpansionLoc(decl->getLocation())))
                        continue;
                    if (const auto* instance = trick::icg::compat::explicitInstantiation(decl))
                    {
                        if (llvm::isa<clang::CXXRecordDecl>(instance))
                            request(instance);
                        else
                            unsupported(ctx, decl, "Only class explicit instantiation directives are supported");
                        continue;
                    }
                    if (llvm::isa<clang::CXXRecordDecl, clang::EnumDecl, clang::TypedefNameDecl, clang::NamespaceDecl,
                                  clang::NamespaceAliasDecl, clang::FunctionDecl, clang::ClassTemplateDecl>(decl))
                        request(llvm::cast<clang::NamedDecl>(decl));
                    else if (!llvm::isa<clang::EmptyDecl, clang::StaticAssertDecl>(decl))
                        unsupported(ctx, decl,
                                    "Only records, class templates, enums, aliases, callables, and namespaces are "
                                    "extracted in this slice");
                }
            }

            void classTemplate(clang::ASTContext& ctx, const clang::NamedDecl* decl)
            {
                const auto* primary = llvm::dyn_cast<clang::ClassTemplateDecl>(decl);
                const auto* partial = llvm::dyn_cast<clang::ClassTemplatePartialSpecializationDecl>(decl);
                const auto* pattern = primary ? primary->getTemplatedDecl() : partial;
                auto node           = common(ctx, decl, "class_template");
                // Clang attaches class attributes to the templated record and
                // documentation to the template declaration. Retain both once.
                if (primary)
                {
                    auto* combined = node.getArray("annotations");
                    for (auto& annotation : annotations(ctx, pattern))
                        if (std::find(combined->begin(), combined->end(), annotation) == combined->end())
                            combined->emplace_back(std::move(annotation));
                }
                node["template_kind"]       = primary ? "primary" : "partial_specialization";
                node["record_tag"]          = pattern->isUnion() ? "union" : (pattern->isClass() ? "class" : "struct");
                node["definition"]          = pattern->isCompleteDefinition();
                node["template_parameters"] = templates->parameters(primary ? primary->getTemplateParameters()
                                                                            : partial->getTemplateParameters());
                node["primary_template_id"] = nullptr;
                node["pattern_spelling"]    = nullptr;
                if (partial)
                {
                    auto id = request(partial->getSpecializedTemplate());
                    if (id.empty())
                        return;
                    node["primary_template_id"] = std::move(id);
                    node["pattern_spelling"]    = node.getString("qualified_name")->str();
                }
                node["capabilities"] = Array {
                    Object { { "name", "template-pattern" },
                            { "status", "unknown" },
                            { "reason_code", "DEPENDENT_TEMPLATE_PATTERN" } }
                };
                publish(decl, std::move(node));
            }

            Value specializationIdentity(const clang::ClassTemplateSpecializationDecl* decl)
            {
                auto primary   = request(decl->getSpecializedTemplate());
                auto arguments = templates->arguments(decl->getTemplateArgs(), decl);
                if (primary.empty() || facts.failed)
                    return nullptr;
                return Object {
                    { "primary_template_id", std::move(primary)   },
                    { "arguments",           std::move(arguments) }
                };
            }

            void specializationFacts(Object& node, const clang::ClassTemplateSpecializationDecl* decl)
            {
                const char* kind = "undeclared";
                switch (decl->getSpecializationKind())
                {
                case clang::TSK_Undeclared:
                    break;
                case clang::TSK_ImplicitInstantiation:
                    kind = "implicit_instantiation";
                    break;
                case clang::TSK_ExplicitSpecialization:
                    kind = "explicit_specialization";
                    break;
                case clang::TSK_ExplicitInstantiationDeclaration:
                    kind = "explicit_instantiation_declaration";
                    break;
                case clang::TSK_ExplicitInstantiationDefinition:
                    kind = "explicit_instantiation_definition";
                    break;
                }
                node["specialization_kind"] = kind;
                auto primary                = request(decl->getSpecializedTemplate());
                if (primary.empty())
                    return;
                node["primary_template_id"]      = std::move(primary);
                node["template_arguments"]       = templates->arguments(decl->getTemplateArgs(), decl);
                node["instantiation_pattern_id"] = nullptr;
                node["instantiation_arguments"]  = nullptr;
                if (auto from = decl->getInstantiatedFrom(); !from.isNull())
                {
                    const clang::NamedDecl* pattern = llvm::dyn_cast<clang::ClassTemplateDecl*>(from);
                    if (!pattern)
                        pattern = llvm::cast<clang::ClassTemplatePartialSpecializationDecl*>(from);
                    auto id = request(pattern);
                    if (!id.empty())
                        node["instantiation_pattern_id"] = std::move(id);
                    node["instantiation_arguments"] = templates->arguments(decl->getTemplateInstantiationArgs(), decl);
                }
                const auto point               = decl->getPointOfInstantiation();
                node["point_of_instantiation"] = point.isValid()
                    ? sources.source(context->getSourceManager(), clang::SourceRange(point), &context->getLangOpts())
                    : Value(nullptr);
            }

            void alias(clang::ASTContext& ctx, const clang::TypedefNameDecl* decl)
            {
                auto node                  = common(ctx, decl, "alias");
                node["type_id"]            = types->get(trick::icg::compat::declarationType(ctx, decl), decl);
                node["underlying_type_id"] = types->get(decl->getUnderlyingType(), decl);
                publish(decl, std::move(node));
            }

            void enumeration(clang::ASTContext& ctx, const clang::EnumDecl* decl)
            {
                auto underlying = decl->getIntegerType();
                if (!decl->isComplete() || underlying.isNull() || decl->isDependentType()
                    || !underlying->isIntegerType())
                {
                    unsupported(ctx, decl, "Enum requires a concrete integral underlying type");
                    return;
                }
                auto node                  = common(ctx, decl, "enum");
                node["type_id"]            = types->get(trick::icg::compat::declarationType(ctx, decl), decl);
                node["anonymous"]          = decl->getIdentifier() == nullptr;
                node["scoped"]             = decl->isScoped();
                node["underlying_fixed"]   = decl->isFixed();
                node["underlying_signed"]  = underlying->isSignedIntegerType();
                node["underlying_type_id"] = types->get(underlying, decl);
                // Opaque fixed enums are complete types without an enumerator body.
                node["complete"]   = true;
                node["definition"] = decl->isCompleteDefinition();
                node["size_bits"]
                    = trick::icg::unsignedInteger(ctx.getTypeSize(trick::icg::compat::declarationType(ctx, decl)));
                // Enum alignment attributes need not match the underlying type.
                node["alignment_bits"]
                    = trick::icg::unsignedInteger(ctx.getTypeAlign(trick::icg::compat::declarationType(ctx, decl)));
                Array values;
                for (const auto* constant : decl->enumerators())
                {
                    auto location
                        = sources.source(ctx.getSourceManager(), constant->getSourceRange(), &ctx.getLangOpts());
                    if (location.kind() == Value::Null)
                        unsupported(ctx, constant, "Enumerator has no supported physical source");
                    llvm::SmallString<64> value;
                    constant->getInitVal().toString(value, 10);
                    values.emplace_back(Object {
                        { "name", constant->getNameAsString() },
                        { "value", value.str().str() },
                        { "source", std::move(location) },
                        { "annotations", annotations(ctx, constant) }
                    });
                }
                node["enumerators"] = std::move(values);
                publish(decl, std::move(node));
            }

            const char* specialKind(const clang::FunctionDecl* decl)
            {
                if (const auto* ctor = llvm::dyn_cast<clang::CXXConstructorDecl>(decl))
                {
                    if (ctor->isCopyConstructor())
                        return "copy_constructor";
                    if (ctor->isMoveConstructor())
                        return "move_constructor";
                    if (ctor->isDefaultConstructor())
                        return "default_constructor";
                }
                if (llvm::isa<clang::CXXDestructorDecl>(decl))
                    return "destructor";
                if (const auto* method = llvm::dyn_cast<clang::CXXMethodDecl>(decl))
                {
                    if (method->isCopyAssignmentOperator())
                        return "copy_assignment";
                    if (method->isMoveAssignmentOperator())
                        return "move_assignment";
                }
                return "none";
            }

            const char* exceptionFact(const clang::FunctionDecl* decl)
            {
                auto* mutableDecl = const_cast<clang::FunctionDecl*>(decl);
                auto* proto       = decl->getType()->getAs<clang::FunctionProtoType>();
                if (!proto)
                    return "unknown";
                if (proto->getExceptionSpecType() == clang::EST_Unevaluated)
                {
                    compiler.getSema().EvaluateImplicitExceptionSpec(decl->getLocation(), mutableDecl);
                    proto = decl->getType()->getAs<clang::FunctionProtoType>();
                }
                if (clang::isUnresolvedExceptionSpec(proto->getExceptionSpecType()))
                    return "unknown";
                switch (proto->canThrow())
                {
                case clang::CT_Cannot:
                    return "true";
                case clang::CT_Can:
                    return "false";
                case clang::CT_Dependent:
                    return "unknown";
                }
                return "unknown";
            }

            Array parameters(clang::ASTContext& ctx, const clang::FunctionDecl* decl)
            {
                Array result;
                for (const auto* parameter : decl->parameters())
                {
                    auto location
                        = sources.source(ctx.getSourceManager(), parameter->getSourceRange(), &ctx.getLangOpts());
                    if (location.kind() == Value::Null)
                        unsupported(ctx, parameter, "Parameter requires physical source evidence");
                    Object item {
                        { "name", parameter->getNameAsString() },
                        { "type_id", types->get(parameter->getType(), decl) },
                        { "original_type_id", types->get(parameter->getOriginalType(), decl) },
                        { "source", std::move(location) },
                        { "annotations", annotations(ctx, parameter) },
                        { "has_default", parameter->hasDefaultArg() },
                        { "default_origin", nullptr },
                        { "default_spelling", nullptr },
                        { "default_source", nullptr }
                    };
                    if (parameter->hasDefaultArg())
                    {
                        item["default_origin"] = parameter->hasInheritedDefaultArg() ? "inherited" : "written";
                        if (parameter->hasUnparsedDefaultArg() || parameter->hasUninstantiatedDefaultArg())
                            unsupported(ctx, parameter, "Unparsed/dependent default arguments are unsupported");
                        else
                        {
                            const auto* expression = parameter->getDefaultArg();
                            auto source = sources.source(ctx.getSourceManager(), expression->getSourceRange(),
                                                         &ctx.getLangOpts());
                            if (source.kind() == Value::Null)
                                unsupported(ctx, parameter, "Default argument requires physical source evidence");
                            std::string spelling;
                            llvm::raw_string_ostream stream(spelling);
                            auto policy = ctx.getPrintingPolicy();
                            trick::icg::compat::anonymousNamesWithoutLocations(policy);
                            expression->printPretty(stream, nullptr, policy);
                            item["default_spelling"] = stream.str();
                            item["default_source"]   = std::move(source);
                        }
                    }
                    result.emplace_back(std::move(item));
                }
                return result;
            }

            void callable(clang::ASTContext& ctx, const clang::FunctionDecl* decl)
            {
                const auto* proto         = decl->getType()->getAs<clang::FunctionProtoType>();
                const bool concreteMember = llvm::isa<clang::CXXMethodDecl>(decl)
                    && decl->getTemplatedKind() == clang::FunctionDecl::TK_MemberSpecialization;
                if (decl->isImplicit()
                    || (decl->getTemplatedKind() != clang::FunctionDecl::TK_NonTemplate && !concreteMember)
                    || decl->isDependentContext() || !proto || proto->getCallConv() != clang::CC_C
                    || proto->getMethodQuals().hasRestrict() || proto->getMethodQuals().hasNonFastQualifiers()
                    || proto->getHasRegParm() || proto->hasExtParameterInfos() || proto->getCmseNSCallAttr())
                {
                    unsupported(ctx, decl,
                                "Only explicit non-template callables with the C calling convention and CV/ref "
                                "qualifiers are supported");
                    return;
                }
                auto node                   = common(ctx, decl, "callable");
                const auto* method          = llvm::dyn_cast<clang::CXXMethodDecl>(decl);
                const auto* ctor            = llvm::dyn_cast<clang::CXXConstructorDecl>(decl);
                const auto* dtor            = llvm::dyn_cast<clang::CXXDestructorDecl>(decl);
                const auto* conversion      = llvm::dyn_cast<clang::CXXConversionDecl>(decl);
                node["callable_kind"]       = ctor ? "constructor"
                    : dtor                         ? "destructor"
                    : conversion                   ? "conversion"
                    : method                       ? "method"
                                                   : "function";
                node["special_member_kind"] = specialKind(decl);
                node["return_type_id"] = ctor || dtor ? Value(nullptr) : Value(types->get(decl->getReturnType(), decl));
                node["parameters"]     = parameters(ctx, decl);
                node["const"]          = method && method->isConst();
                node["volatile"]       = method && method->isVolatile();
                node["static"]         = method && method->isStatic();
                const auto* linkage    = trick::icg::compat::linkage(decl->getLinkageInternal());
                if (!linkage)
                {
                    facts.diagnose("error", "ICG_INVALID_LINKAGE", "Callable has invalid semantic linkage",
                                   sources.source(ctx.getSourceManager(), decl->getSourceRange(), &ctx.getLangOpts()));
                    return;
                }
                node["linkage"] = linkage;
                switch (decl->getLanguageLinkage())
                {
                case clang::CLanguageLinkage:
                    node["language_linkage"] = "c";
                    break;
                case clang::CXXLanguageLinkage:
                    node["language_linkage"] = "c++";
                    break;
                case clang::NoLanguageLinkage:
                    node["language_linkage"] = "none";
                    break;
                }
                node["ref_qualifier"]      = proto->getRefQualifier() == clang::RQ_LValue ? "lvalue"
                    : proto->getRefQualifier() == clang::RQ_RValue                        ? "rvalue"
                                                                                          : "none";
                node["noexcept"]           = exceptionFact(decl);
                node["virtual"]            = method && method->isVirtual();
                node["pure"]               = trick::icg::compat::pureVirtual(decl);
                node["final"]              = decl->hasAttr<clang::FinalAttr>();
                node["deleted"]            = decl->isDeleted();
                node["explicit"]           = ctor ? ctor->isExplicit() : conversion && conversion->isExplicit();
                node["constexpr"]          = decl->isConstexpr();
                node["variadic"]           = decl->isVariadic();
                node["calling_convention"] = "c";
                node["user_provided"]      = decl->isUserProvided();
                Array overrides;
                Array implicitOverrides;
                std::set<std::string> overrideIDs;
                std::set<std::string> implicitOverrideIDs;
                if (method)
                {
                    for (const auto* overridden : method->overridden_methods())
                        if (overridden->isImplicit() && llvm::isa<clang::CXXDestructorDecl>(overridden))
                            request(overridden->getParent(), implicitOverrideIDs);
                        else
                            request(overridden, overrideIDs);
                }
                for (const auto& id : overrideIDs)
                    overrides.emplace_back(id);
                for (const auto& id : implicitOverrideIDs)
                    implicitOverrides.emplace_back(id);
                node["overridden_declaration_ids"]                = std::move(overrides);
                node["overridden_implicit_destructor_record_ids"] = std::move(implicitOverrides);
                std::vector<const clang::FunctionDecl*> redecls(decl->redecls_begin(), decl->redecls_end());
                auto& sm = ctx.getSourceManager();
                std::sort(redecls.begin(), redecls.end(), [&sm](const auto* a, const auto* b)
                          { return sm.isBeforeInTranslationUnit(a->getBeginLoc(), b->getBeginLoc()); });
                Array occurrences;
                Array allAnnotations;
                bool defined   = false;
                bool defaulted = false;
                for (const auto* occurrence : redecls)
                {
                    auto evidence = common(ctx, occurrence, "callable");
                    Object item {
                        { "source", std::move(*evidence.get("source")) },
                        { "parameters", parameters(ctx, occurrence) },
                        { "annotations", annotations(ctx, occurrence) },
                        { "definition", occurrence->isThisDeclarationADefinition() }
                    };
                    auto lexical = parentID(occurrence->getLexicalDeclContext());
                    if (!lexical.empty())
                        item["lexical_parent_id"] = lexical;
                    for (const auto& annotation : *item.getArray("annotations"))
                        allAnnotations.emplace_back(Value(annotation));
                    defined   |= occurrence->isThisDeclarationADefinition();
                    defaulted |= occurrence->isDefaulted();
                    if (!method && occurrence->getStorageClass() == clang::SC_Static)
                        node["static"] = true;
                    occurrences.emplace_back(std::move(item));
                }
                node["definition"]     = defined;
                node["defaulted"]      = defaulted;
                node["redeclarations"] = std::move(occurrences);
                node["annotations"]    = std::move(allAnnotations);
                publish(decl, std::move(node));
            }

            Array specialMembers(clang::ASTContext& ctx, const clang::CXXRecordDecl* decl)
            {
                Array result;
                if (decl->isCompleteDefinition())
                    compiler.getSema().ForceDeclarationOfImplicitMembers(const_cast<clang::CXXRecordDecl*>(decl));
                for (const auto* kind : { "default_constructor", "copy_constructor", "move_constructor",
                                          "copy_assignment", "move_assignment", "destructor" })
                {
                    Object slot {
                        { "kind",            kind                                                    },
                        { "state",           decl->isCompleteDefinition() ? "suppressed" : "unknown" },
                        { "declaration_ids", Array { }                                               },
                        { "deleted",         nullptr                                                 },
                        { "trivial",         nullptr                                                 },
                        { "virtual",         nullptr                                                 },
                        { "noexcept",        nullptr                                                 }
                    };
                    std::set<std::string> declared;
                    if (decl->isCompleteDefinition())
                        for (const auto* method : decl->methods())
                            if (std::string(specialKind(method)) == kind)
                            {
                                if (method->isImplicit())
                                {
                                    slot["state"]    = "implicit";
                                    slot["deleted"]  = method->isDeleted();
                                    slot["trivial"]  = method->isTrivial();
                                    slot["virtual"]  = method->isVirtual();
                                    slot["noexcept"] = exceptionFact(method);
                                }
                                else
                                    request(method, declared);
                            }
                    if (!declared.empty())
                    {
                        if (*slot.getString("state") == "implicit")
                            unsupported(ctx, decl, "Conflicting implicit and user-declared special members");
                        slot["state"] = "user_declared";
                        for (const auto& id : declared)
                            slot.getArray("declaration_ids")->emplace_back(id);
                    }
                    result.emplace_back(std::move(slot));
                }
                return result;
            }

            void record(clang::ASTContext& ctx, const clang::CXXRecordDecl* decl)
            {
                if (decl->isDependentType() || decl->getDescribedClassTemplate())
                {
                    unsupported(ctx, decl, "Only non-template records are supported");
                    return;
                }
                auto node = common(ctx, decl, "record");
                if (const auto* specialization = llvm::dyn_cast<clang::ClassTemplateSpecializationDecl>(decl))
                    specializationFacts(node, specialization);
                node["type_id"]                = types->get(trick::icg::compat::declarationType(ctx, decl), decl);
                node["record_tag"]             = decl->isUnion() ? "union" : (decl->isClass() ? "class" : "struct");
                node["anonymous"]              = decl->getIdentifier() == nullptr;
                node["definition"]             = decl->isCompleteDefinition();
                node["complete"]               = decl->isCompleteDefinition();
                node["bases"]                  = Array { };
                node["virtual_base_offsets"]   = Array { };
                node["field_ids"]              = Array { };
                node["nested_declaration_ids"] = Array { };
                node["callable_ids"]           = Array { };
                node["special_members"]        = specialMembers(ctx, decl);
                if (!decl->isCompleteDefinition())
                {
                    node["size_bits"]                  = nullptr;
                    node["alignment_bits"]             = nullptr;
                    node["data_size_bits"]             = nullptr;
                    node["non_virtual_size_bits"]      = nullptr;
                    node["non_virtual_alignment_bits"] = nullptr;
                    node["capabilities"]               = Array {
                        Object { { "name", "frontend-record-layout" },
                                { "status", "unknown" },
                                { "reason_code", "INCOMPLETE_TYPE" } }
                    };
                    publish(decl, std::move(node));
                    return;
                }
                Array nested;
                Array callables;
                std::set<std::string> callableIDs;
                std::set<std::string> nestedIDs;
                std::map<const clang::FieldDecl*, uint64_t> bitWidths;
                bool unsupportedMembers = false;
                for (const auto* member : decl->decls())
                {
                    const auto* field          = llvm::dyn_cast<clang::FieldDecl>(member);
                    const bool anonymousMember = field && field->isAnonymousStructOrUnion();
                    if ((member->isImplicit() && !anonymousMember)
                        || llvm::isa<clang::AccessSpecDecl, clang::StaticAssertDecl>(member))
                        continue;
                    if (const auto* friendship = llvm::dyn_cast<clang::FriendDecl>(member))
                    {
                        // Declaration-only friends do not add record members.
                        // Tolerate the TRICK_ICG idiom without inferring access
                        // grants or traversing a friend's unrelated dependency
                        // graph. Definitions and templates remain fail-closed.
                        const auto* type     = friendship->getFriendType();
                        const auto* function = llvm::dyn_cast_or_null<clang::FunctionDecl>(friendship->getFriendDecl());
                        const bool concreteType
                            = type && !type->getType()->isDependentType() && type->getType()->isRecordType();
                        const bool declarationOnly = function && !function->doesThisDeclarationHaveABody()
                            && !function->isDeleted() && !function->isDefaulted()
                            && function->getTemplatedKind() == clang::FunctionDecl::TK_NonTemplate;
                        if (friendship->isUnsupportedFriend() || friendship->getFriendTypeNumTemplateParameterLists()
                            || (!concreteType && !declarationOnly))
                        {
                            unsupported(ctx, member,
                                        "Only concrete type and non-template function friend declarations "
                                        "without definitions are supported; access grants are not modeled");
                            unsupportedMembers = true;
                        }
                        continue;
                    }
                    if (const auto* function = llvm::dyn_cast<clang::FunctionDecl>(member))
                    {
                        auto id             = request(function);
                        unsupportedMembers |= id.empty();
                        if (!id.empty() && callableIDs.insert(id).second)
                            callables.emplace_back(id);
                        continue;
                    }
                    if (llvm::isa<clang::CXXRecordDecl, clang::EnumDecl, clang::TypedefNameDecl,
                                  clang::ClassTemplateDecl>(member))
                    {
                        auto id             = request(llvm::cast<clang::NamedDecl>(member));
                        unsupportedMembers |= id.empty();
                        if (!id.empty() && nestedIDs.insert(id).second)
                            nested.emplace_back(id);
                        continue;
                    }
                    if (!field || (field->getIdentifier() == nullptr && !anonymousMember && !field->isBitField()))
                    {
                        unsupported(
                            ctx, member,
                            "Only data members, callables, anonymous aggregates, and nested records/enums/aliases "
                            "are supported");
                        unsupportedMembers = true;
                    }
                    else if (field->isBitField())
                    {
                        clang::Expr::EvalResult width;
                        if (field->getBitWidth()->isValueDependent() || !field->getBitWidth()->EvaluateAsInt(width, ctx)
                            || width.Val.getInt().isNegative() || width.Val.getInt().getActiveBits() > 32)
                        {
                            unsupported(ctx, field,
                                        "Bitfield requires a concrete width within Clang's 32-bit layout range");
                            unsupportedMembers = true;
                        }
                        else
                            bitWidths.emplace(field, width.Val.getInt().getZExtValue());
                    }
                }
                if (unsupportedMembers)
                    return;
                const auto& layout = ctx.getASTRecordLayout(decl);
                node["abstract"]   = decl->isAbstract();
                // The declaration query uses TR1/layout rules, which can
                // disagree with the language trait (notably on Darwin).
                node["pod"]             = trick::icg::compat::declarationType(ctx, decl).isPODType(ctx);
                node["standard_layout"] = decl->isStandardLayout();
                node["trivial"]         = decl->isTrivial();
                node["size_bits"] = trick::icg::unsignedInteger(static_cast<uint64_t>(layout.getSize().getQuantity())
                                                                * ctx.getCharWidth());
                node["alignment_bits"] = trick::icg::unsignedInteger(
                    static_cast<uint64_t>(layout.getAlignment().getQuantity()) * ctx.getCharWidth());
                node["data_size_bits"] = trick::icg::unsignedInteger(
                    static_cast<uint64_t>(layout.getDataSize().getQuantity()) * ctx.getCharWidth());
                node["non_virtual_size_bits"] = trick::icg::unsignedInteger(
                    static_cast<uint64_t>(layout.getNonVirtualSize().getQuantity()) * ctx.getCharWidth());
                node["non_virtual_alignment_bits"] = trick::icg::unsignedInteger(
                    static_cast<uint64_t>(layout.getNonVirtualAlignment().getQuantity()) * ctx.getCharWidth());
                Array bases;
                for (const auto& base : decl->bases())
                {
                    const auto* target = base.getType()->getAsCXXRecordDecl();
                    auto location = sources.source(ctx.getSourceManager(), base.getSourceRange(), &ctx.getLangOpts());
                    if (!target || !target->getDefinition() || base.isPackExpansion() || location.kind() == Value::Null)
                    {
                        unsupported(ctx, decl, "Base requires a concrete record definition and physical source");
                        continue;
                    }
                    auto targetID = request(target);
                    auto typeID   = types->get(base.getType(), decl);
                    if (targetID.empty() || typeID.empty())
                        continue;
                    // A virtual base has no fixed offset relative to an arbitrary
                    // base subobject. Its complete-object position lives below.
                    Value offset = nullptr;
                    if (!base.isVirtual())
                        offset = trick::icg::unsignedInteger(
                            static_cast<uint64_t>(layout.getBaseClassOffset(target).getQuantity())
                            * ctx.getCharWidth());
                    bases.emplace_back(Object {
                        { "declaration_id", std::move(targetID)                        },
                        { "type_id",        std::move(typeID)                          },
                        { "access",         access(base.getAccessSpecifier())          },
                        { "written_access", access(base.getAccessSpecifierAsWritten()) },
                        { "virtual",        base.isVirtual()                           },
                        { "offset_bits",    std::move(offset)                          },
                        { "source",         std::move(location)                        }
                    });
                }
                node["bases"] = std::move(bases);
                // All virtual bases, including indirect/shared diamond bases,
                // appear once. Map order is stable, unlike AST pointer order.
                std::map<std::string, Value> virtualOffsets;
                for (const auto& base : decl->vbases())
                {
                    const auto* target = base.getType()->getAsCXXRecordDecl();
                    if (!target || !target->getDefinition() || base.isPackExpansion())
                    {
                        unsupported(ctx, decl, "Virtual base requires a concrete record definition");
                        continue;
                    }
                    auto id = request(target);
                    if (id.empty())
                        continue;
                    virtualOffsets.emplace(std::move(id),
                                           trick::icg::unsignedInteger(
                                               static_cast<uint64_t>(layout.getVBaseClassOffset(target).getQuantity())
                                               * ctx.getCharWidth()));
                }
                Array virtualBases;
                for (auto& entry : virtualOffsets)
                    virtualBases.emplace_back(Object {
                        { "declaration_id", entry.first             },
                        { "offset_bits",    std::move(entry.second) }
                    });
                node["virtual_base_offsets"]   = std::move(virtualBases);
                node["nested_declaration_ids"] = std::move(nested);
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
                    data["type_id"]            = types->get(field->getType(), field);
                    data["static"]             = false;
                    data["mutable"]            = field->isMutable();
                    data["bitfield"]           = field->isBitField();
                    data["anonymous_member"]   = field->isAnonymousStructOrUnion();
                    data["bit_width"]
                        = field->isBitField() ? trick::icg::unsignedInteger(bitWidths.at(field)) : Value(nullptr);
                    data["offset_bits"] = trick::icg::unsignedInteger(layout.getFieldOffset(index++));
                    if (field->isBitField())
                        data["capabilities"] = Array {
                            Object { { "name", "field-address" },
                                    { "status", "unsupported" },
                                    { "reason_code", "BITFIELD_NOT_ADDRESSABLE" } }
                        };
                    auto id = declarationID(field);
                    if (id.empty())
                        continue;
                    fields.emplace_back(std::move(id));
                    publish(field, std::move(data));
                }
                node["field_ids"]    = std::move(fields);
                node["callable_ids"] = std::move(callables);
                publish(decl, std::move(node));
            }

        public:
            Consumer(Facts& facts, Sources& sources, clang::CompilerInstance& compiler)
                : facts(facts)
                , sources(sources)
                , compiler(compiler)
            {
            }
            void HandleTranslationUnit(clang::ASTContext& ctx) override
            {
                if (ctx.getDiagnostics().hasErrorOccurred())
                    return;
                auto& sm                             = ctx.getSourceManager();
                context                              = &ctx;
                facts.provenance["translation_unit"] = sources.file(sm, sm.getMainFileID());
                identities                           = std::make_unique<trick::icg::DeclarationIdentity>(
                    facts, ctx, [this, &sm](clang::SourceLocation location) { return sources.point(sm, location); },
                    [this, &ctx](const clang::Decl* decl)
                    { return sources.source(ctx.getSourceManager(), decl->getSourceRange(), &ctx.getLangOpts()); },
                    [this](const clang::ClassTemplateSpecializationDecl* decl)
                    { return specializationIdentity(decl); });
                types = std::make_unique<trick::icg::TypeGraph>(
                    facts, ctx, compiler.getSema(), [this](const clang::NamedDecl* decl) { return request(decl); },
                    [this, &ctx](const clang::Decl* decl, const std::string& message)
                    {
                        facts.diagnose(
                            "error", "ICG_UNSUPPORTED_TYPE", message,
                            sources.source(ctx.getSourceManager(), decl->getSourceRange(), &ctx.getLangOpts()));
                    });
                templates = std::make_unique<trick::icg::TemplateFacts>(
                    ctx, *types, [this](const clang::NamedDecl* decl) { return request(decl); },
                    [this, &ctx](clang::SourceRange range)
                    { return sources.source(ctx.getSourceManager(), range, &ctx.getLangOpts()); },
                    [this, &ctx](const clang::Decl* decl, const std::string& message)
                    { unsupported(ctx, decl, message); });
                facts.provenance["target_triple"] = ctx.getTargetInfo().getTriple().str();
                selectMainFile(ctx, ctx.getTranslationUnitDecl());
                // A worklist closes record/alias references without recursively
                // expanding self-referential records during type interning.
                for (size_t index = 0; index < pending.size(); ++index)
                    if (llvm::isa<clang::ClassTemplateDecl, clang::ClassTemplatePartialSpecializationDecl>(
                            pending[index]))
                        classTemplate(ctx, pending[index]);
                    else if (const auto* value = llvm::dyn_cast<clang::CXXRecordDecl>(pending[index]))
                        record(ctx, value);
                    else if (const auto* value = llvm::dyn_cast<clang::EnumDecl>(pending[index]))
                        enumeration(ctx, value);
                    else if (const auto* value = llvm::dyn_cast<clang::TypedefNameDecl>(pending[index]))
                        alias(ctx, value);
                    else if (const auto* value = llvm::dyn_cast<clang::NamespaceDecl>(pending[index]))
                        namespaceDecl(ctx, value);
                    else if (const auto* value = llvm::dyn_cast<clang::FunctionDecl>(pending[index]))
                        callable(ctx, value);
                    else
                        namespaceAlias(ctx, llvm::cast<clang::NamespaceAliasDecl>(pending[index]));
                if (facts.failed)
                    return;
                // Namespace membership is the selected closure, never all sibling
                // declarations in a referenced header. Node maps order these IDs.
                for (const auto& entry : facts.declarations)
                    if (auto parent = entry.second.getString("semantic_parent_id"))
                    {
                        if (auto* members = facts.declarations.at(parent->str()).getArray("declaration_ids"))
                            members->emplace_back(entry.first);
                        // Implicit member-template specializations need not occur
                        // in their enclosing record's decls(). Preserve lexical
                        // member order, then append the selected instances by ID.
                        if (entry.second.getString("specialization_kind"))
                            if (auto* members = facts.declarations.at(parent->str()).getArray("nested_declaration_ids"))
                                if (std::none_of(members->begin(), members->end(), [&entry](const auto& value)
                                                 { return value.getAsString() == entry.first; }))
                                    members->emplace_back(entry.first);
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
                return std::make_unique<Consumer>(facts, sources, ci);
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
                if (++i < args.size() && !args[i].empty() && args[i][0] != '-')
                    continue;
                facts.diagnose("error", "ICG_ARGUMENT_VALUE", "Expected a non-flag value for " + arg.str());
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
                { "schema_version", 2                        },
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
    std::string root = cwd.str().str();
    std::map<std::string, std::string> roots {
        { "resource-dir", ICG_RESOURCE_DIR }
    };
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
        else if (arg == "--path-root" && i + 1 < argc)
        {
            llvm::StringRef mapping(argv[++i]);
            auto pair = mapping.split('=');
            if (pair.first.empty() || pair.second.empty() || pair.first == "source"
                || pair.first.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789-") != llvm::StringRef::npos
                || pair.first.front() < 'a' || pair.first.front() > 'z')
                facts.diagnose("error", "ICG_PATH_ROOT", "Expected NAME=DIR; use --source-root for source");
            else if (roots.count(pair.first.str()) && pair.first != "resource-dir")
                facts.diagnose("error", "ICG_PATH_ROOT", "Duplicate named root: " + pair.first.str());
            else
                roots[pair.first.str()] = pair.second.str();
        }
        else if (arg == "--help")
        {
            llvm::outs() << "Usage: trick-icg-extract [--source-root DIR] [--path-root NAME=DIR] "
                            "[--diagnostics-format=json] HEADER -- [CLANG FLAGS]\n"
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
    roots["source"] = root;
    std::set<std::string> rootPaths;
    for (auto& entry : roots)
    {
        entry.second = realPath(entry.second);
        if (entry.second.empty() || !llvm::sys::fs::is_directory(entry.second))
            facts.diagnose("error", "ICG_PATH_ROOT", "Named root must be an existing directory: " + entry.first);
        else if (!rootPaths.insert(entry.second).second)
            facts.diagnose("error", "ICG_PATH_ROOT", "Named roots must not map to the same directory: " + entry.first);
    }
    if (!input.empty() && realPath(input).empty())
        facts.diagnose("error", "ICG_INPUT_READ", "Cannot resolve input: " + input);
    checkArguments(arguments, facts);
    if (facts.failed)
    {
        printDiagnostics(facts, jsonDiagnostics);
        return 2;
    }

    Sources sources(facts, roots);
    Diagnostics diagnostics(facts, sources);
    Factory factory(facts, sources);
    std::vector<std::string> flags { "-x",
                                     "c++",
                                     "-std=c++17",
                                     "-resource-dir",
                                     roots.at("resource-dir"),
                                     "-fparse-all-comments",
                                     "-fsyntax-only",
                                     "-fno-caret-diagnostics",
                                     "-Werror=unknown-warning-option",
                                     "-Wno-pragma-once-outside-header" };
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
    facts.provenance["extractor_version"]    = ICG_EXTRACTOR_VERSION;
    facts.provenance["identity_version"]     = trick::icg::DeclarationIdentityVersion;
    facts.provenance["graph_digest_version"] = trick::icg::GraphDigestVersion;
    facts.provenance["frontend_api"]         = "libtooling";
    facts.provenance["frontend_version"]     = clang::getClangFullVersion();
    facts.provenance["language_standard"]    = "c++17";
    facts.provenance["working_directory"]    = cwd.str().str();
    Object pathRoots;
    for (const auto& entry : roots)
        pathRoots[entry.first] = entry.second;
    facts.provenance["path_roots"]  = std::move(pathRoots);
    facts.provenance["environment"] = std::move(environment);
    int result                      = tool.run(&factory);
    if (result && !facts.failed)
        facts.diagnose("error", "ICG_FRONTEND_FAILED", "Clang invocation did not complete");
    if (!facts.failed && !facts.provenance.getString("translation_unit"))
        facts.diagnose("error", "ICG_NO_TRANSLATION_UNIT", "No translation unit was extracted");
    printDiagnostics(facts, jsonDiagnostics);
    if (facts.failed)
        return 1;
    facts.provenance["graph_digest"] = facts.graphDigest();
    // Evidence fingerprint, NOT a production cache key: exact arguments, paths,
    // environment, frontend facts, and contents of observed physical inputs.
    facts.provenance["input_digest"] = digest(serialize(facts.document()));
    llvm::outs() << serialize(facts.document()) << '\n';
    return 0;
}
