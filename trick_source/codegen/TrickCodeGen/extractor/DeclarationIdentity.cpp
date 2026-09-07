#include "DeclarationIdentity.hh"

#include "clang/AST/ASTContext.h"
#include "clang/AST/DeclCXX.h"
#include "clang/Basic/SourceManager.h"
#include "clang/Index/USRGeneration.h"

namespace trick::icg
{
    DeclarationIdentity::DeclarationIdentity(Facts& facts, clang::ASTContext& context,
                                             std::function<llvm::json::Value(clang::SourceLocation)> point)
        : facts(facts)
        , context(context)
        , point(std::move(point))
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
        value.fromSource = !decl->getIdentifier() || value.usr.empty();
        std::string parentID;
        const auto* parent = decl->getDeclContext();
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
            if (location.empty())
                facts.diagnose("error", "ICG_IDENTITY_SOURCE",
                               "Cannot form a physical source identity for " + decl->getNameAsString());
            else
            {
                llvm::json::Object identity {
                    { "kind",     decl->getDeclKindName() },
                    { "parent",   parentID                },
                    { "name",     decl->getNameAsString() },
                    { "location", std::move(location)     }
                };
                if (const auto* ns = llvm::dyn_cast<clang::NamespaceDecl>(decl); ns && ns->isAnonymousNamespace())
                    identity["translation_unit"] = facts.provenance.getString("translation_unit")->str();
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
