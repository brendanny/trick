#include "DeclarationIdentity.hh"

#include "ClangCompat.hh"

#include "clang/AST/ASTContext.h"
#include "clang/AST/DeclCXX.h"
#include "clang/AST/DeclTemplate.h"
#include "clang/Basic/SourceManager.h"

namespace trick::icg
{
    // Extractor-owned tags, not Clang's internal display strings or enum values.
    // Keep distinctions even where multiple kinds share a wire node shape.
    static llvm::StringRef identityKind(const clang::NamedDecl* decl)
    {
        switch (decl->getKind())
        {
        case clang::Decl::Namespace:
            return "namespace";
        case clang::Decl::NamespaceAlias:
            return "namespace-alias";
        case clang::Decl::CXXRecord:
            return "record";
        case clang::Decl::ClassTemplate:
            return "class-template";
        case clang::Decl::ClassTemplatePartialSpecialization:
            return "class-template-partial";
        case clang::Decl::ClassTemplateSpecialization:
            return "class-template-specialization";
        case clang::Decl::Enum:
            return "enum";
        case clang::Decl::Typedef:
            return "typedef";
        case clang::Decl::TypeAlias:
            return "type-alias";
        case clang::Decl::Field:
            return "field";
        case clang::Decl::Function:
            return "function";
        case clang::Decl::CXXMethod:
            return "method";
        case clang::Decl::CXXConstructor:
            return "constructor";
        case clang::Decl::CXXDestructor:
            return "destructor";
        case clang::Decl::CXXConversion:
            return "conversion";
        default:
            return { };
        }
    }

    DeclarationIdentity::DeclarationIdentity(
        Facts& facts, clang::ASTContext& context, std::function<llvm::json::Value(clang::SourceLocation)> point,
        std::function<llvm::json::Value(const clang::ClassTemplateSpecializationDecl*)> specialization)
        : facts(facts)
        , context(context)
        , point(std::move(point))
        , specialization(std::move(specialization))
    {
    }

    std::string DeclarationIdentity::anchor(clang::SourceLocation location)
    {
        // Raw encodings are only local memoization keys. Hash both origin edges:
        // a macro argument's caller follows its spelling and would otherwise
        // lose the distinct parameter substitution sites in the macro body.
        auto known = anchors.find(location.getRawEncoding());
        if (known != anchors.end())
            return known->second;
        auto& sm                 = context.getSourceManager();
        llvm::json::Value origin = nullptr;
        if (location.isMacroID())
        {
            auto range    = sm.getImmediateExpansionRange(location);
            auto spelling = anchor(sm.getImmediateSpellingLoc(location));
            auto begin    = anchor(range.getBegin());
            auto end      = anchor(range.getEnd());
            if (spelling.empty() || begin.empty() || end.empty())
                return { };
            origin = llvm::json::Object {
                { "spelling",        spelling                         },
                { "expansion_begin", begin                            },
                { "expansion_end",   end                              },
                { "argument",        sm.isMacroArgExpansion(location) }
            };
        }
        else
            origin = point(location);
        if (origin.kind() == llvm::json::Value::Null)
            return { };
        // Memoized digests keep shared spelling/expansion subgraphs linear in
        // size instead of recursively duplicating the same origin tree in JSON.
        auto id = digest(serialize(origin));
        anchors.emplace(location.getRawEncoding(), id);
        return id;
    }

    const DeclarationID& DeclarationIdentity::get(const clang::NamedDecl* decl)
    {
        decl       = llvm::cast<clang::NamedDecl>(decl->getCanonicalDecl());
        auto known = identities.find(decl);
        if (known != identities.end())
            return known->second;

        DeclarationID value;
        llvm::SmallString<128> rawUSR;
        if (!clang::index::generateUSRForDecl(decl, rawUSR))
            value.usr = rawUSR.str().str();
        // Constructors, conversions, and operators have semantic names without
        // IdentifierInfo. Their USRs still distinguish overload signatures.
        value.fromSource     = (!decl->getIdentifier() && !llvm::isa<clang::FunctionDecl>(decl)) || value.usr.empty();
        const auto* instance = llvm::dyn_cast<clang::ClassTemplateSpecializationDecl>(decl);
        if (llvm::isa<clang::ClassTemplatePartialSpecializationDecl>(decl))
            instance = nullptr;
        // Instantiated members share their pattern's physical locations. Include
        // canonical semantic arguments before source identity propagates to them.
        value.fromSource |= instance != nullptr;
        const bool translationUnitLocal
            = llvm::isa<clang::FunctionDecl>(decl) && compat::translationUnitLocalLinkage(decl->getLinkageInternal());
        value.fromSource |= translationUnitLocal;
        std::string parentID;
        const auto* parent = decl->getDeclContext();
        while (!parent->isTranslationUnit())
        {
            const auto* parentDecl = clang::Decl::castFromDeclContext(parent);
            const auto* linkage    = llvm::dyn_cast<clang::LinkageSpecDecl>(parentDecl);
            if (!linkage)
                break;
            parent = linkage->getDeclContext();
        }
        if (!parent->isTranslationUnit())
        {
            const auto* parentDecl = clang::Decl::castFromDeclContext(parent);
            if (const auto* named = llvm::dyn_cast<clang::NamedDecl>(parentDecl);
                named && llvm::isa<clang::NamespaceDecl, clang::CXXRecordDecl>(named))
            {
                const auto& parentIdentity  = get(named);
                parentID                    = parentIdentity.id;
                value.fromSource           |= parentIdentity.fromSource;
            }
            else
                facts.diagnose("error", "ICG_UNSUPPORTED_CONTEXT",
                               "Declaration identity requires a namespace or record context");
        }
        if (value.fromSource)
        {
            auto location = anchor(decl->getLocation());
            auto kind     = identityKind(decl);
            if (kind.empty())
                facts.diagnose("error", "ICG_IDENTITY_KIND", "Declaration has no supported identity kind");
            else if (location.empty())
                facts.diagnose("error", "ICG_IDENTITY_SOURCE",
                               "Cannot form a physical source identity for " + decl->getNameAsString());
            else
            {
                llvm::json::Object identity {
                    { "version",  DeclarationIdentityVersion },
                    { "kind",     kind                       },
                    { "parent",   parentID                   },
                    { "name",     decl->getNameAsString()    },
                    { "location", std::move(location)        }
                };
                if (const auto* ns = llvm::dyn_cast<clang::NamespaceDecl>(decl); ns && ns->isAnonymousNamespace())
                    identity["translation_unit"] = facts.provenance.getString("translation_unit")->str();
                if (translationUnitLocal)
                    identity["translation_unit"] = facts.provenance.getString("translation_unit")->str();
                if (instance)
                {
                    auto key = specialization(instance);
                    if (key.kind() == llvm::json::Value::Null)
                        return identities.emplace(decl, std::move(value)).first->second;
                    identity["specialization"] = std::move(key);
                }
                value.id = "decl:" + digest("source:" + serialize(std::move(identity)));
            }
        }
        else
            value.id = "decl:" + digest(value.usr);

        if (!value.id.empty())
        {
            auto inserted = owners.emplace(value.id, decl);
            if (!inserted.second && inserted.first->second != decl)
                facts.diagnose("error", "ICG_IDENTITY_COLLISION",
                               "Distinct canonical declarations produced the same ID: " + value.id);
        }
        return identities.emplace(decl, std::move(value)).first->second;
    }
}
