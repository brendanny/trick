#include "Config.hh"
#include "DeclarationIdentity.hh"
#include "Facts.hh"
#include "TypeGraph.hh"

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
#include "clang/Lex/Lexer.h"
#include "clang/Lex/PPCallbacks.h"
#include "clang/Lex/Preprocessor.h"
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
                const auto* entry = sm.getFileEntryForID(fid);
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
            clang::ASTContext* context = nullptr;
            std::unique_ptr<trick::icg::TypeGraph> types;
            std::unique_ptr<trick::icg::DeclarationIdentity> identities;
            std::vector<const clang::NamedDecl*> pending;
            std::set<std::string> queued;

            std::string declarationID(const clang::NamedDecl* decl) { return identities->get(decl).id; }

            std::string parentID(const clang::DeclContext* parent)
            {
                if (parent->isTranslationUnit())
                    return { };
                const auto* decl = clang::Decl::castFromDeclContext(parent);
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
                if (const auto* record = llvm::dyn_cast<clang::CXXRecordDecl>(decl))
                    decl = record->getDefinition() ? record->getDefinition() : record->getCanonicalDecl();
                else if (const auto* enumeration = llvm::dyn_cast<clang::EnumDecl>(decl))
                    decl
                        = enumeration->getDefinition() ? enumeration->getDefinition() : enumeration->getCanonicalDecl();
                else if (const auto* alias = llvm::dyn_cast<clang::TypedefNameDecl>(decl))
                    decl = alias->getCanonicalDecl();
                else if (const auto* ns = llvm::dyn_cast<clang::NamespaceDecl>(decl))
                    decl = ns->getCanonicalDecl();
                else if (llvm::isa<clang::NamespaceAliasDecl>(decl))
                    decl = llvm::cast<clang::NamedDecl>(decl->getCanonicalDecl());
                else
                {
                    unsupported(*context, decl,
                                "Only records, enums, aliases, and namespace declaration references are supported");
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

            Array annotations(clang::ASTContext& ctx, const clang::NamedDecl* decl)
            {
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
                return annotations;
            }

            Object common(clang::ASTContext& ctx, const clang::NamedDecl* decl, const char* kind)
            {
                auto location = sources.source(ctx.getSourceManager(), decl->getSourceRange(), &ctx.getLangOpts());
                const auto& identity = identities->get(decl);
                if (location.kind() == Value::Null || identity.id.empty())
                    unsupported(ctx, decl, "Declaration has no supported physical source or stable identity");
                clang::PrintingPolicy policy(ctx.getLangOpts());
                policy.AnonymousTagLocations   = false;
                policy.SuppressInlineNamespace = false;
                std::string qualifiedName;
                llvm::raw_string_ostream nameStream(qualifiedName);
                decl->printQualifiedName(nameStream, policy);
                Object node {
                    { "id", declarationID(decl) },
                    { "kind", kind },
                    { "name", decl->getNameAsString() },
                    { "qualified_name", qualifiedName },
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
                facts.declarations.emplace(declarationID(decl), std::move(node));
            }

            void namespaceAlias(clang::ASTContext& ctx, const clang::NamespaceAliasDecl* decl)
            {
                auto node                   = common(ctx, decl, "namespace_alias");
                node["target_namespace_id"] = request(decl->getAliasedNamespace());
                facts.declarations.emplace(declarationID(decl), std::move(node));
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
                    if (!sm.isWrittenInMainFile(sm.getExpansionLoc(decl->getLocation())))
                        continue;
                    if (llvm::isa<clang::CXXRecordDecl, clang::EnumDecl, clang::TypedefNameDecl, clang::NamespaceDecl,
                                  clang::NamespaceAliasDecl>(decl))
                        request(llvm::cast<clang::NamedDecl>(decl));
                    else if (!llvm::isa<clang::EmptyDecl, clang::StaticAssertDecl>(decl))
                        unsupported(ctx, decl,
                                    "Only records, enums, aliases, and namespaces are extracted in this slice");
                }
            }

            void alias(clang::ASTContext& ctx, const clang::TypedefNameDecl* decl)
            {
                auto node                  = common(ctx, decl, "alias");
                node["type_id"]            = types->get(ctx.getTypedefType(decl), decl);
                node["underlying_type_id"] = types->get(decl->getUnderlyingType(), decl);
                facts.declarations.emplace(declarationID(decl), std::move(node));
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
                node["type_id"]            = types->get(ctx.getEnumType(decl), decl);
                node["anonymous"]          = decl->getIdentifier() == nullptr;
                node["scoped"]             = decl->isScoped();
                node["underlying_fixed"]   = decl->isFixed();
                node["underlying_signed"]  = underlying->isSignedIntegerType();
                node["underlying_type_id"] = types->get(underlying, decl);
                // Opaque fixed enums are complete types without an enumerator body.
                node["complete"]   = true;
                node["definition"] = decl->isCompleteDefinition();
                node["size_bits"]  = trick::icg::unsignedInteger(ctx.getTypeSize(ctx.getEnumType(decl)));
                // Enum alignment attributes need not match the underlying type.
                node["alignment_bits"] = trick::icg::unsignedInteger(ctx.getTypeAlign(ctx.getEnumType(decl)));
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
                facts.declarations.emplace(declarationID(decl), std::move(node));
            }

            void record(clang::ASTContext& ctx, const clang::CXXRecordDecl* decl)
            {
                if (decl->isDependentType() || decl->getDescribedClassTemplate()
                    || llvm::isa<clang::ClassTemplateSpecializationDecl>(decl))
                {
                    unsupported(ctx, decl, "Only non-template records are supported");
                    return;
                }
                auto node                      = common(ctx, decl, "record");
                node["type_id"]                = types->get(ctx.getRecordType(decl), decl);
                node["record_tag"]             = decl->isUnion() ? "union" : (decl->isClass() ? "class" : "struct");
                node["anonymous"]              = decl->getIdentifier() == nullptr;
                node["definition"]             = decl->isCompleteDefinition();
                node["complete"]               = decl->isCompleteDefinition();
                node["bases"]                  = Array { };
                node["virtual_base_offsets"]   = Array { };
                node["field_ids"]              = Array { };
                node["nested_declaration_ids"] = Array { };
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
                    facts.declarations.emplace(declarationID(decl), std::move(node));
                    return;
                }
                Array nested;
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
                    if (llvm::isa<clang::CXXRecordDecl, clang::EnumDecl, clang::TypedefNameDecl>(member))
                    {
                        auto id             = request(llvm::cast<clang::NamedDecl>(member));
                        unsupportedMembers |= id.empty();
                        if (nestedIDs.insert(id).second)
                            nested.emplace_back(id);
                        continue;
                    }
                    if (!field || (field->getIdentifier() == nullptr && !anonymousMember && !field->isBitField()))
                    {
                        unsupported(ctx, member,
                                    "Only data members, anonymous aggregates, and nested records/enums/aliases "
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
                const auto& layout      = ctx.getASTRecordLayout(decl);
                node["abstract"]        = decl->isAbstract();
                node["pod"]             = decl->isPOD();
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
                    // A virtual base has no fixed offset relative to an arbitrary
                    // base subobject. Its complete-object position lives below.
                    Value offset = nullptr;
                    if (!base.isVirtual())
                        offset = trick::icg::unsignedInteger(
                            static_cast<uint64_t>(layout.getBaseClassOffset(target).getQuantity())
                            * ctx.getCharWidth());
                    bases.emplace_back(Object {
                        { "declaration_id", request(target) },
                        { "type_id", types->get(base.getType(), decl) },
                        { "access", access(base.getAccessSpecifier()) },
                        { "written_access", access(base.getAccessSpecifierAsWritten()) },
                        { "virtual", base.isVirtual() },
                        { "offset_bits", std::move(offset) },
                        { "source", std::move(location) }
                    });
                }
                node["bases"] = std::move(bases);
                // All virtual bases, including indirect/shared diamond bases,
                // appear once. Map order is stable, unlike AST pointer order.
                std::map<std::string, Value> virtualOffsets;
                for (const auto& base : decl->vbases())
                {
                    const auto* target = base.getType()->getAsCXXRecordDecl();
                    virtualOffsets.emplace(request(target),
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
                context                              = &ctx;
                facts.provenance["translation_unit"] = sources.file(sm, sm.getMainFileID());
                identities                           = std::make_unique<trick::icg::DeclarationIdentity>(
                    facts, ctx, [this, &sm](clang::SourceLocation location) { return sources.point(sm, location); });
                types = std::make_unique<trick::icg::TypeGraph>(
                    facts, ctx, [this](const clang::NamedDecl* decl) { return request(decl); },
                    [this, &ctx](const clang::Decl* decl, const std::string& message)
                    {
                        facts.diagnose(
                            "error", "ICG_UNSUPPORTED_TYPE", message,
                            sources.source(ctx.getSourceManager(), decl->getSourceRange(), &ctx.getLangOpts()));
                    });
                facts.provenance["target_triple"] = ctx.getTargetInfo().getTriple().str();
                selectMainFile(ctx, ctx.getTranslationUnitDecl());
                // A worklist closes record/alias references without recursively
                // expanding self-referential records during type interning.
                for (size_t index = 0; index < pending.size(); ++index)
                    if (const auto* value = llvm::dyn_cast<clang::CXXRecordDecl>(pending[index]))
                        record(ctx, value);
                    else if (const auto* value = llvm::dyn_cast<clang::EnumDecl>(pending[index]))
                        enumeration(ctx, value);
                    else if (const auto* value = llvm::dyn_cast<clang::TypedefNameDecl>(pending[index]))
                        alias(ctx, value);
                    else if (const auto* value = llvm::dyn_cast<clang::NamespaceDecl>(pending[index]))
                        namespaceDecl(ctx, value);
                    else
                        namespaceAlias(ctx, llvm::cast<clang::NamespaceAliasDecl>(pending[index]));
                if (facts.failed)
                    return;
                // Namespace membership is the selected closure, never all sibling
                // declarations in a referenced header. Node maps order these IDs.
                for (const auto& entry : facts.declarations)
                    if (auto parent = entry.second.getString("semantic_parent_id"))
                        if (auto* members = facts.declarations.at(parent->str()).getArray("declaration_ids"))
                            members->emplace_back(entry.first);
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
    facts.provenance["extractor_version"] = ICG_EXTRACTOR_VERSION;
    facts.provenance["frontend_api"]      = "libtooling";
    facts.provenance["frontend_version"]  = clang::getClangFullVersion();
    facts.provenance["language_standard"] = "c++17";
    facts.provenance["working_directory"] = cwd.str().str();
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
    // Evidence fingerprint, NOT a production cache key: exact arguments, paths,
    // environment, frontend facts, and contents of observed physical inputs.
    facts.provenance["input_digest"] = digest(serialize(facts.document()));
    llvm::outs() << serialize(facts.document()) << '\n';
    return 0;
}
