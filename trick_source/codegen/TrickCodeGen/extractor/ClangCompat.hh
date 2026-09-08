#pragma once

#include "Config.hh"

#include "clang/AST/ASTContext.h"
#include "clang/AST/Comment.h"
#include "clang/AST/DeclTemplate.h"
#include "clang/AST/Expr.h"
#include "clang/Basic/SourceManager.h"
#include "clang/Basic/Version.h"
#include "clang/Lex/PPCallbacks.h"
#include "clang/Sema/Sema.h"
#include "clang/Sema/Template.h"
#if CLANG_VERSION_MAJOR >= 23
#include "clang/UnifiedSymbolResolution/USRGeneration.h"
#else
#include "clang/Index/USRGeneration.h"
#endif

static_assert(CLANG_VERSION_MAJOR == ICG_LLVM_VERSION_MAJOR, "Clang headers must match the LLVM package");

namespace trick::icg::compat
{
    inline const clang::TypedefNameDecl* instantiatedAlias(clang::Sema& sema, const clang::TypedefNameDecl* alias,
                                                           const clang::Decl* owner)
    {
        if (!owner)
            return nullptr;
        if (!alias->getDeclContext()->isDependentContext())
            return alias;
        const auto* named = llvm::dyn_cast<clang::NamedDecl>(owner);
        if (!named || owner->getDeclContext()->isDependentContext())
            return nullptr;
        // Non-dependent typedef sugar can still name a template's pattern even
        // inside an instantiated method. Let Sema map it using the real owner,
        // including partial specializations and nested instantiation levels.
        auto* scope = const_cast<clang::DeclContext*>(owner->getDeclContext());
        if (llvm::isa<clang::CXXRecordDecl, clang::FunctionDecl>(owner))
            scope = clang::Decl::castToDeclContext(const_cast<clang::Decl*>(owner));
        clang::Sema::ContextRAII current(sema, scope);
        const auto arguments = sema.getTemplateInstantiationArgs(named);
        const auto* result   = llvm::dyn_cast_or_null<clang::TypedefNameDecl>(
            sema.FindInstantiatedDecl(owner->getLocation(), const_cast<clang::TypedefNameDecl*>(alias), arguments));
        return result && !result->getDeclContext()->isDependentContext() ? result : nullptr;
    }

    inline const clang::NamedDecl* explicitInstantiation(const clang::Decl* decl)
    {
#if CLANG_VERSION_MAJOR >= 23
        if (const auto* directive = llvm::dyn_cast<clang::ExplicitInstantiationDecl>(decl))
            return directive->getSpecialization();
#else
        (void)decl;
#endif
        return nullptr;
    }

    inline clang::QualType declarationType(clang::ASTContext& context, const clang::TypeDecl* decl)
    {
        // Keep the TypeDecl overload: LLVM 22 deletes the derived-declaration
        // overloads, while an explicit empty qualifier would mean global scope.
        return context.getTypeDeclType(decl);
    }

    inline void anonymousNamesWithoutLocations(clang::PrintingPolicy& policy)
    {
#if CLANG_VERSION_MAJOR >= 23
        policy.AnonymousTagNameStyle = static_cast<unsigned>(clang::PrintingPolicy::AnonymousTagMode::Plain);
#else
        policy.AnonymousTagLocations = false;
#endif
    }

    inline void structuralTypeNames(clang::PrintingPolicy& policy, clang::QualType type)
    {
        anonymousNamesWithoutLocations(policy);
#if CLANG_VERSION_MAJOR >= 22
        // Qualifiers/keywords now live on tag/typedef nodes. Preserve the
        // fully scoped, tag-free display used before ElaboratedType removal.
        policy.FullyQualifiedName            = llvm::isa<clang::TagType, clang::TypedefType>(type.getTypePtr());
        policy.SuppressTagKeywordInAnonNames = true;
#else
        (void)type;
#endif
    }

    inline bool pureVirtual(const clang::FunctionDecl* decl)
    {
#if CLANG_VERSION_MAJOR >= 18
        return decl->isPureVirtual();
#else
        return decl->isPure();
#endif
    }

    inline const clang::RawComment* localRawComment(clang::ASTContext& context, const clang::Decl* decl, bool& valid)
    {
        valid = true;
#if CLANG_VERSION_MAJOR >= 23
        // LLVM 23 made raw per-declaration lookup private. Its public local
        // parsed-comment query still provides occurrence-specific attachment.
        // Recover the original bytes from the owning raw-comment list, never
        // the redeclaration fallback used by documentation rendering.
        const auto* local = context.getLocalCommentForDeclUncached(decl);
        if (!local)
            return nullptr;
        const auto& sm   = context.getSourceManager();
        const auto begin = local->getBeginLoc();
        if (begin.isValid())
        {
            const auto location = sm.getDecomposedLoc(begin);
            if (const auto* comments = context.Comments.getCommentsInFile(location.first))
            {
                auto after = comments->upper_bound(location.second);
                if (after != comments->begin())
                {
                    const auto* raw = std::prev(after)->second;
                    if (sm.getFileOffset(raw->getEndLoc()) >= location.second)
                        return raw;
                }
            }
        }
        // Empty parsed comments may not have a content location. Accept the
        // public raw query only when it identifies this exact occurrence.
        const clang::Decl* original = nullptr;
        const auto* raw             = context.getRawCommentForAnyRedecl(decl, &original);
        if (raw && original == decl)
            return raw;
        valid = false;
        return nullptr;
#else
        return context.getRawCommentForDeclNoCache(decl);
#endif
    }

    // Keep frontend version boundaries out of the owned facts/identity model.
    class PPCallbacks : public clang::PPCallbacks
    {
        public:
            void InclusionDirective(clang::SourceLocation hash, const clang::Token&, llvm::StringRef name, bool angled,
                                    clang::CharSourceRange range, clang::OptionalFileEntryRef entry, llvm::StringRef,
                                    llvm::StringRef, const clang::Module*,
#if CLANG_VERSION_MAJOR >= 19
                                    bool,
#endif
                                    clang::SrcMgr::CharacteristicKind kind) final
            {
                inclusion(hash, name, angled, range, entry, kind);
            }

            virtual void inclusion(clang::SourceLocation, llvm::StringRef, bool, clang::CharSourceRange,
                                   clang::OptionalFileEntryRef, clang::SrcMgr::CharacteristicKind) = 0;
    };

    inline clang::QualType withoutElaboratedType(clang::ASTContext& context, clang::QualType type)
    {
#if CLANG_VERSION_MAJOR < 22
        if (const auto* elaborated = llvm::dyn_cast<clang::ElaboratedType>(type.getTypePtr()))
            return context.getQualifiedType(elaborated->getNamedType(), type.getLocalQualifiers());
#else
        const clang::TypeDecl* decl = nullptr;
        if (const auto* tag = llvm::dyn_cast<clang::TagType>(type.getTypePtr()))
            decl = tag->getDecl();
        else if (const auto* alias = llvm::dyn_cast<clang::TypedefType>(type.getTypePtr()))
            decl = alias->getDecl();
        if (decl)
            return context.getQualifiedType(declarationType(context, decl), type.getLocalQualifiers());
#endif
        return type;
    }

    inline clang::QualType defaultType(const clang::TemplateTypeParmDecl* decl)
    {
#if CLANG_VERSION_MAJOR >= 19
        return decl->getDefaultArgument().getArgument().getAsType();
#else
        return decl->getDefaultArgument();
#endif
    }

    inline clang::SourceRange defaultTypeRange(const clang::TemplateTypeParmDecl* decl)
    {
#if CLANG_VERSION_MAJOR >= 19
        return decl->getDefaultArgument().getSourceRange();
#else
        return decl->getDefaultArgumentInfo()->getTypeLoc().getSourceRange();
#endif
    }

    inline const clang::Expr* defaultExpression(const clang::NonTypeTemplateParmDecl* decl)
    {
#if CLANG_VERSION_MAJOR >= 19
        return decl->getDefaultArgument().getSourceExpression();
#else
        return decl->getDefaultArgument();
#endif
    }

    inline bool translationUnitLocalLinkage(clang::Linkage value)
    {
#if CLANG_VERSION_MAJOR >= 18
        return value == clang::Linkage::Internal || value == clang::Linkage::UniqueExternal;
#else
        return value == clang::InternalLinkage || value == clang::UniqueExternalLinkage;
#endif
    }

    inline const char* linkage(clang::Linkage value)
    {
        switch (value)
        {
#if CLANG_VERSION_MAJOR >= 18
        case clang::Linkage::None:
            return "none";
        case clang::Linkage::Internal:
            return "internal";
        case clang::Linkage::UniqueExternal:
            return "unique_external";
        case clang::Linkage::VisibleNone:
            return "visible_no_linkage";
        case clang::Linkage::Module:
            return "module";
        case clang::Linkage::External:
            return "external";
        case clang::Linkage::Invalid:
            break;
#else
        case clang::NoLinkage:
            return "none";
        case clang::InternalLinkage:
            return "internal";
        case clang::UniqueExternalLinkage:
            return "unique_external";
        case clang::VisibleNoLinkage:
            return "visible_no_linkage";
        case clang::ModuleLinkage:
            return "module";
        case clang::ExternalLinkage:
            return "external";
#endif
        }
        return nullptr;
    }
}
