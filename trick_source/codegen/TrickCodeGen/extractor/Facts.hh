#pragma once

#include "TypeNode.hh"

#include "llvm/Support/JSON.h"

#include <map>
#include <string>

namespace trick::icg
{

    // Owned wire values only. No AST, SourceManager, StringRef, or frontend lifetime
    // escapes the adapter. The schema is the public process boundary.
    // Types have a typed value model; declaration/file builders still use JSON.
    struct Facts
    {
            llvm::json::Object provenance;
            std::map<std::string, llvm::json::Object> files;
            std::map<std::string, TypeNode> types;
            std::map<std::string, llvm::json::Object> declarations;
            llvm::json::Array diagnostics;
            bool failed = false;

            void diagnose(std::string severity, std::string code, std::string message,
                          llvm::json::Value source = nullptr);
            llvm::json::Object document() const;
    };

    std::string digest(llvm::StringRef bytes);
    // Preserve exact integers in JSON readers with binary64 number storage.
    llvm::json::Value unsignedInteger(uint64_t value);
    // Sort object keys recursively as well as the node maps. Ordered semantic arrays
    // (fields, includes, diagnostics, arguments) keep their original order.
    std::string serialize(const llvm::json::Value& value);

} // namespace trick::icg
