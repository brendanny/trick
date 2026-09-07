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

    llvm::json::Value DeclarationIdentity::anchor(clang::SourceLocation location)
    {
        auto& sm = context.getSourceManager();
        llvm::json::Array frames;
        // The complete caller chain distinguishes two uses of an anonymous-record
        // macro inside one outer expansion, even when their final source ranges
        // and ultimate spelling locations coincide.
        while (location.isMacroID())
        {
            auto spelling = point(sm.getSpellingLoc(location));
            if (spelling.kind() == llvm::json::Value::Null)
                return nullptr;
            frames.emplace_back(std::move(spelling));
            location = sm.getImmediateMacroCallerLoc(location);
        }
        auto physical = point(location);
        if (physical.kind() == llvm::json::Value::Null)
            return nullptr;
        frames.emplace_back(std::move(physical));
        return frames;
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
            if (location.kind() == llvm::json::Value::Null)
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
