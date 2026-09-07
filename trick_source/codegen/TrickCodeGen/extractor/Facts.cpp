#include "Facts.hh"

#include "llvm/ADT/StringExtras.h"
#include "llvm/Support/FormatVariadic.h"
#include "llvm/Support/SHA256.h"
#include "llvm/Support/raw_ostream.h"

namespace trick::icg
{

    llvm::json::Value unsignedInteger(uint64_t value)
    {
        if (value > 9007199254740991ULL)
            return std::to_string(value);
        return value;
    }

    std::string digest(llvm::StringRef bytes)
    {
        llvm::SHA256 hash;
        hash.update(bytes);
        return llvm::toHex(hash.final(), true);
    }

    static void write(const llvm::json::Value& value, llvm::raw_ostream& out)
    {
        if (const auto* object = value.getAsObject())
        {
            std::map<std::string, const llvm::json::Value*> sorted;
            for (const auto& entry : *object)
            {
                sorted.emplace(entry.first.str(), &entry.second);
            }
            out << '{';
            bool first = true;
            for (const auto& entry : sorted)
            {
                if (!first)
                    out << ',';
                first = false;
                out << llvm::formatv("{0}", llvm::json::Value(entry.first)) << ':';
                write(*entry.second, out);
            }
            out << '}';
        }
        else if (const auto* array = value.getAsArray())
        {
            out << '[';
            bool first = true;
            for (const auto& entry : *array)
            {
                if (!first)
                    out << ',';
                first = false;
                write(entry, out);
            }
            out << ']';
        }
        else
        {
            out << llvm::formatv("{0}", value);
        }
    }

    std::string serialize(const llvm::json::Value& value)
    {
        std::string result;
        llvm::raw_string_ostream out(result);
        write(value, out);
        return result;
    }

    void Facts::diagnose(std::string severity, std::string code, std::string message, llvm::json::Value source)
    {
        failed |= severity == "error" || severity == "fatal";
        diagnostics.emplace_back(llvm::json::Object {
            { "severity", std::move(severity) },
            { "code",     std::move(code)     },
            { "message",  std::move(message)  },
            { "source",   std::move(source)   }
        });
    }

    llvm::json::Object Facts::document() const
    {
        auto nodes = [](const auto& values)
        {
            llvm::json::Array result;
            for (const auto& entry : values)
                result.emplace_back(llvm::json::Object(entry.second));
            return result;
        };
        llvm::json::Array typeNodes;
        for (const auto& entry : types)
            typeNodes.emplace_back(entry.second.json());
        return llvm::json::Object {
            { "schema_version", 3                              },
            { "document_kind",  "trick.icg.extracted-facts"    },
            { "provenance",     llvm::json::Object(provenance) },
            { "files",          nodes(files)                   },
            { "types",          std::move(typeNodes)           },
            { "declarations",   nodes(declarations)            },
            { "diagnostics",    llvm::json::Array(diagnostics) }
        };
    }

} // namespace trick::icg
