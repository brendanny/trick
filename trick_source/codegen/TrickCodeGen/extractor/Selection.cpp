#include "Selection.hh"

#include "ClangCompat.hh"

#include <algorithm>

namespace trick::icg
{
    void Selection::run(clang::ASTContext& ctx, const std::function<std::string(const clang::NamedDecl*)>& request,
                        const std::function<void(const clang::Decl*, const std::string&)>& unsupported)
    {
        auto& sm = ctx.getSourceManager();
        if (requestedPaths.empty())
            selectedFiles.insert(sources.file(sm, sm.getMainFileID()));
        else
            for (const auto& path : requestedPaths)
            {
                auto found = std::find_if(facts.files.begin(), facts.files.end(), [&path](const auto& item)
                                          { return item.second.getObject("path")->getString("real") == path; });
                if (found == facts.files.end())
                    facts.diagnose("error", "ICG_SELECTION_FILE",
                                   "Selected file was not observed in this translation unit: " + path);
                else
                    selectedFiles.insert(found->first);
            }
        std::map<unsigned, bool> selectedLocations;
        auto selected = [&](clang::SourceLocation loc)
        {
            loc = sm.getExpansionLoc(loc);
            if (loc.isInvalid())
                return false;
            const auto fid = sm.getFileID(loc);
            auto found     = selectedLocations.find(fid.getHashValue());
            if (found != selectedLocations.end())
                return found->second;
            const bool result = selectedFiles.count(sources.file(sm, fid));
            selectedLocations.emplace(fid.getHashValue(), result);
            return result;
        };
        auto root = [&](const clang::NamedDecl* decl, clang::SourceRange range)
        {
            auto id       = request(decl);
            auto location = sources.source(sm, range, &ctx.getLangOpts());
            if (id.empty())
                return;
            if (location.kind() == llvm::json::Value::Null)
            {
                unsupported(decl, "Selected declaration has no supported physical source");
                return;
            }
            llvm::json::Object entry {
                { "declaration_id", id                  },
                { "source",         std::move(location) }
            };
            if (occurrences.insert(serialize(llvm::json::Object(entry))).second)
                roots.emplace_back(std::move(entry));
        };
        std::function<void(const clang::DeclContext*)> visit = [&](const clang::DeclContext* scope)
        {
            for (const auto* decl : scope->decls())
            {
                if (decl->isImplicit())
                    continue;
                if (const auto* ns = llvm::dyn_cast<clang::NamespaceDecl>(decl))
                    visit(ns);
                if (const auto* linkage = llvm::dyn_cast<clang::LinkageSpecDecl>(decl))
                {
                    visit(linkage);
                    continue;
                }
                if (const auto* pattern = llvm::dyn_cast<clang::ClassTemplateDecl>(decl))
                    for (const auto* instance : pattern->specializations())
                        if (clang::isTemplateExplicitInstantiationOrSpecialization(instance->getSpecializationKind())
                            && selected(instance->getPointOfInstantiation()))
                            root(instance, clang::SourceRange(instance->getPointOfInstantiation()));
                if (!selected(decl->getLocation()))
                    continue;
                if (const auto* instance = compat::explicitInstantiation(decl))
                {
                    if (llvm::isa<clang::CXXRecordDecl>(instance))
                        root(instance, decl->getSourceRange());
                    else
                        unsupported(decl, "Only class explicit instantiation directives are supported");
                    continue;
                }
                if (llvm::isa<clang::CXXRecordDecl, clang::EnumDecl, clang::TypedefNameDecl, clang::NamespaceDecl,
                              clang::NamespaceAliasDecl, clang::FunctionDecl, clang::ClassTemplateDecl>(decl))
                    root(llvm::cast<clang::NamedDecl>(decl), decl->getSourceRange());
                else if (!llvm::isa<clang::EmptyDecl, clang::StaticAssertDecl>(decl))
                    unsupported(decl,
                                "Only records, class templates, enums, aliases, callables, and namespaces are "
                                "extracted in this slice");
            }
        };
        visit(ctx.getTranslationUnitDecl());
        // Roots form a set of physical occurrences, not Clang's specialization
        // traversal order. Keep request evidence stable across frontend majors.
        std::sort(roots.begin(), roots.end(), [](const auto& a, const auto& b) { return serialize(a) < serialize(b); });
        llvm::json::Array files;
        for (const auto& id : selectedFiles)
            files.emplace_back(id);
        facts.provenance["selection"] = llvm::json::Object {
            { "mode",           requestedPaths.empty() ? "main-file" : "explicit-files" },
            { "required_facts", "supported-declaration-closure"                         },
            { "file_ids",       std::move(files)                                        },
            { "roots",          std::move(roots)                                        }
        };
    }
}
