#pragma once

#include "llvm/Support/JSON.h"

#include <map>
#include <string>

namespace trick::icg
{

    // Owned wire values only. No AST, SourceManager, StringRef, or frontend lifetime
    // escapes the adapter. The schema is the public process boundary; this small
    // builder will gain typed nodes as the structural type graph grows.
    struct Facts
    {
            llvm::json::Object provenance;
            std::map<std::string, llvm::json::Object> files;
            std::map<std::string, llvm::json::Object> types;
            std::map<std::string, llvm::json::Object> declarations;
            llvm::json::Array diagnostics;
            bool failed = false;

            void diagnose(std::string severity, std::string code, std::string message,
                          llvm::json::Value source = nullptr);
            llvm::json::Object document() const;
    };

    std::string digest(llvm::StringRef bytes);
    // Sort object keys recursively as well as the node maps. Ordered semantic arrays
    // (fields, includes, diagnostics, arguments) keep their original order.
    std::string serialize(const llvm::json::Value& value);

} // namespace trick::icg
