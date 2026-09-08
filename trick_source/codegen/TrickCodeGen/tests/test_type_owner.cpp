#include "ClangCompat.hh"
#include "TypeGraph.hh"

#include "clang/Tooling/Tooling.h"

#include <iostream>

int main()
{
    // A real parsed template supplies the typedef sugar that previously sent a
    // null owner through the alias adapter and into a source-range callback.
    auto ast = clang::tooling::buildASTFromCodeWithArgs("template<class T> struct A { using ref = int&; };",
                                                        { "-std=c++17" }, "owner.hh");
    if (!ast || !ast->hasSema())
        return 1;
    const clang::TypedefNameDecl* alias = nullptr;
    auto& context                       = ast->getASTContext();
    for (const auto* decl : context.getTranslationUnitDecl()->decls())
        if (const auto* pattern = llvm::dyn_cast<clang::ClassTemplateDecl>(decl))
            for (const auto* member : pattern->getTemplatedDecl()->decls())
                if (const auto* value = llvm::dyn_cast<clang::TypedefNameDecl>(member))
                    alias = value;
    if (!alias)
        return 2;

    auto& sema = ast->getSema();
    if (trick::icg::compat::instantiatedAlias(sema, alias, nullptr)
        || trick::icg::compat::instantiatedAlias(sema, alias, context.getTranslationUnitDecl()))
        return 3;
    const clang::QualType cases[] = { context.IntTy, trick::icg::compat::declarationType(context, alias) };
    for (const auto type : cases)
    {
        trick::icg::Facts facts;
        bool callbackCalled = false;
        trick::icg::TypeGraph types(
            facts, context, sema,
            [&callbackCalled](const clang::NamedDecl*)
            {
                callbackCalled = true;
                return "unexpected";
            },
            [&callbackCalled](const clang::Decl*, const std::string&) { callbackCalled = true; });
        if (!types.get(type, nullptr).empty() || !facts.failed || callbackCalled || !facts.types.empty()
            || !facts.declarations.empty() || facts.diagnostics.size() != 1)
            return 4;
        const auto* diagnostic = facts.diagnostics.front().getAsObject();
        if (!diagnostic || diagnostic->getString("code") != "ICG_TYPE_OWNER"
            || diagnostic->getString("severity") != "error" || !diagnostic->get("source")
            || diagnostic->get("source")->kind() != llvm::json::Value::Null)
            return 5;
    }
    std::cout << "Missing owners fail before alias resolution, callbacks, or type interning\n";
}
