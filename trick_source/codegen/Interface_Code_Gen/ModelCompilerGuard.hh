#ifndef TRICK_MODEL_COMPILER_GUARD_HH
#define TRICK_MODEL_COMPILER_GUARD_HH

#include "HeaderSearchDirs.hh"

#include "clang/Lex/Lexer.h"
#include "clang/Lex/PPCallbacks.h"
#include "clang/Lex/Preprocessor.h"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <map>
#include <regex>
#include <sstream>
#include <stdexcept>

// Fail closed for compiler-dependent model declarations. This does not change
// Clang's system-header dialect or claim general ABI equivalence with GCC.
class ModelCompilerGuard final : public clang::PPCallbacks
{
    public:
        ModelCompilerGuard(clang::Preprocessor& pp, HeaderSearchDirs& dirs, const std::string& filename)
            : pp(pp)
            , dirs(dirs)
        {
            std::ifstream input(filename);
            if (!input)
            {
                throw std::runtime_error("Cannot read model compiler predefines: " + filename);
            }
            std::string line;
            while (std::getline(input, line))
            {
                std::istringstream words(line);
                std::string directive, name, value;
                words >> directive >> name;
                if (directive == "#trick_feature")
                {
                    words >> value;
                    if (value != "0" && value != "1")
                        throw std::runtime_error("Invalid feature presence in model compiler profile");
                    features[name] = value == "1";
                    continue;
                }
                if (directive != "#define" || name.compare(0, 2, "__") != 0)
                {
                    continue;
                }
                std::getline(words, value);
                name        = name.substr(0, name.find('('));
                model[name] = compact(value);
            }
            if (!model.count("__cplusplus") || features.size() != 6)
            {
                throw std::runtime_error("Invalid C++ model compiler predefines: " + filename);
            }
        }
        void MacroExpands(const clang::Token& token, const clang::MacroDefinition&, clang::SourceRange range,
                          const clang::MacroArgs*) override
        {
            check(token.getIdentifierInfo()->getName().str(), range.getBegin());
        }
        void Defined(const clang::Token& token, const clang::MacroDefinition&, clang::SourceRange range) override
        {
            check(token.getIdentifierInfo()->getName().str(), range.getBegin(), true);
        }
        void Ifdef(clang::SourceLocation loc, const clang::Token& token, const clang::MacroDefinition&) override
        {
            check(token.getIdentifierInfo()->getName().str(), loc, true);
        }
        void Ifndef(clang::SourceLocation loc, const clang::Token& token, const clang::MacroDefinition&) override
        {
            check(token.getIdentifierInfo()->getName().str(), loc, true);
        }
        void If(clang::SourceLocation loc, clang::SourceRange range, ConditionValueKind) override
        {
            condition(loc, range);
        }
        void Elif(clang::SourceLocation loc, clang::SourceRange range, ConditionValueKind,
                  clang::SourceLocation) override
        {
            condition(loc, range);
        }

    private:
        clang::Preprocessor& pp;
        HeaderSearchDirs& dirs;
        std::map<std::string, std::string> model;
        std::map<std::string, bool> features;
        static std::string compact(std::string value)
        {
            value.erase(std::remove_if(value.begin(), value.end(), [](unsigned char c) { return std::isspace(c); }),
                        value.end());
            return value;
        }
        bool user(clang::SourceLocation loc)
        {
            auto& sm = pp.getSourceManager();
            loc      = sm.getExpansionLoc(loc);
            if (loc.isInvalid() || sm.isInSystemHeader(loc))
            {
                return false;
            }
            auto name = sm.getFilename(loc).str();
            return !name.empty() && dirs.isPathInUserDir(name) && !dirs.isPathExcludedFromICG(name);
        }
        void condition(clang::SourceLocation loc, clang::SourceRange range)
        {
            if (!user(loc))
            {
                return;
            }
            auto text = clang::Lexer::getSourceText(clang::CharSourceRange::getTokenRange(range), pp.getSourceManager(),
                                                    pp.getLangOpts())
                            .str();
            const std::regex identifier("\\b__[A-Za-z0-9_]+\\b");
            for (std::sregex_iterator it(text.begin(), text.end(), identifier), end; it != end; ++it)
            {
                // Defined/Ifdef and MacroExpands handle defined identifiers,
                // distinguishing availability tests from actual operator calls.
                if (!pp.getMacroDefinition(pp.getIdentifierInfo(it->str())).getMacroInfo())
                    check(it->str(), loc);
            }
        }
        void check(const std::string& name, clang::SourceLocation loc, bool presence_only = false)
        {
            // Check model predefines and compiler identity / feature probes that may
            // exist only in Clang. Ordinary user and library macros are unaffected.
            bool tracked = model.count(name) || name == "__clang__" || name == "__GNUC__" || name == "__GNUG__"
                || name.compare(0, 8, "__clang_") == 0 || name.compare(0, 6, "__has_") == 0;
            if (!tracked || !user(loc))
            {
                return;
            }
            auto* info   = pp.getMacroDefinition(pp.getIdentifierInfo(name)).getMacroInfo();
            auto feature = features.find(name);
            if (feature != features.end())
            {
                if (feature->second == (info != nullptr))
                {
                    if (presence_only || !info || name == "__has_include" || name == "__has_include_next"
                        || name == "__has_cpp_attribute")
                        return;
                    // Presence does not establish equal answers for arbitrary
                    // builtin, attribute or language-feature arguments.
                    auto id = pp.getDiagnostics().getCustomDiagID(
                        clang::DiagnosticsEngine::Error,
                        "ICG cannot verify model compiler result for feature query %0; this SDK only supports "
                        "availability tests for this operator");
                    pp.getDiagnostics().Report(pp.getSourceManager().getExpansionLoc(loc), id) << name;
                    return;
                }
            }
            std::string value;
            if (info)
            {
                for (const auto& token : info->tokens())
                {
                    value += pp.getSpelling(token);
                }
            }
            auto expected = model.find(name);
            if (feature == features.end() && expected != model.end() && info && !info->isFunctionLike()
                && compact(value) == expected->second)
            {
                return;
            }
            if (feature == features.end() && expected == model.end() && !info)
            {
                return;
            }
            auto id = pp.getDiagnostics().getCustomDiagID(
                clang::DiagnosticsEngine::Error,
                "model compiler and ICG disagree on predefined macro %0; compiler-dependent model declarations are not "
                "supported by this SDK");
            pp.getDiagnostics().Report(pp.getSourceManager().getExpansionLoc(loc), id) << name;
        }
};
#endif
