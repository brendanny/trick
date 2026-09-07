#include "TemplateFacts.hh"

#include "clang/AST/ASTContext.h"
#include "clang/AST/Expr.h"

namespace trick::icg
{
    using llvm::json::Array;
    using llvm::json::Object;
    using llvm::json::Value;

    TemplateFacts::TemplateFacts(clang::ASTContext& context, TypeGraph& types,
                                 std::function<std::string(const clang::NamedDecl*)> request,
                                 std::function<Value(clang::SourceRange)> source,
                                 std::function<void(const clang::Decl*, const std::string&)> unsupported)
        : context(context)
        , types(types)
        , request(std::move(request))
        , source(std::move(source))
        , unsupported(std::move(unsupported))
    {
    }

    Value TemplateFacts::argument(const clang::TemplateArgument& value, const clang::Decl* owner)
    {
        auto typeID = [this, owner](clang::QualType type)
        {
            return types.get(context.getCanonicalType(type), owner);
        };
        switch (value.getKind())
        {
        case clang::TemplateArgument::Type:
        {
            auto id = typeID(value.getAsType());
            if (!id.empty())
                return Object {
                    { "kind",    "type"        },
                    { "type_id", std::move(id) }
                };
            break;
        }
        case clang::TemplateArgument::Integral:
        {
            auto id = typeID(value.getIntegralType());
            if (id.empty())
                break;
            llvm::SmallString<64> number;
            const auto& integral = value.getAsIntegral();
            integral.toString(number, 10);
            return Object {
                { "kind",      "integral"             },
                { "type_id",   std::move(id)          },
                { "value",     number.str().str()     },
                { "bit_width", integral.getBitWidth() },
                { "signed",    integral.isSigned()    }
            };
        }
        case clang::TemplateArgument::NullPtr:
        {
            auto id = typeID(value.getNullPtrType());
            if (!id.empty())
                return Object {
                    { "kind",    "null_pointer" },
                    { "type_id", std::move(id)  }
                };
            break;
        }
        case clang::TemplateArgument::Template:
        {
            const auto* target = value.getAsTemplate().getAsTemplateDecl();
            if (!llvm::isa_and_nonnull<clang::ClassTemplateDecl>(target))
            {
                unsupported(owner, "Template arguments require a class-template target");
                break;
            }
            auto id = request(target);
            if (!id.empty())
                return Object {
                    { "kind",           "template"    },
                    { "declaration_id", std::move(id) }
                };
            break;
        }
        case clang::TemplateArgument::Pack:
        {
            Array elements;
            for (const auto& element : value.pack_elements())
            {
                auto node = argument(element, owner);
                if (node.kind() == Value::Null)
                    return nullptr;
                elements.emplace_back(std::move(node));
            }
            return Object {
                { "kind",     "pack"              },
                { "elements", std::move(elements) }
            };
        }
        default:
            unsupported(owner,
                        "Only concrete type, integral, null-pointer, class-template, and pack arguments are supported");
        }
        return nullptr;
    }

    Array TemplateFacts::arguments(const clang::TemplateArgumentList& values, const clang::Decl* owner)
    {
        Array result;
        for (const auto& value : values.asArray())
        {
            auto node = argument(value, owner);
            if (node.kind() != Value::Null)
                result.emplace_back(std::move(node));
        }
        return result;
    }

    Array TemplateFacts::parameters(const clang::TemplateParameterList* values)
    {
        Array result;
        auto policy                    = context.getPrintingPolicy();
        policy.AnonymousTagLocations   = false;
        policy.SuppressInlineNamespace = false;
        for (const auto* parameter : *values)
        {
            Object node {
                { "name",             parameter->getNameAsString()        },
                { "pack",             parameter->isParameterPack()        },
                { "source",           source(parameter->getSourceRange()) },
                { "parameters",       Array { }                           },
                { "type_spelling",    nullptr                             },
                { "type_dependent",   nullptr                             },
                { "default_spelling", nullptr                             },
                { "default_source",   nullptr                             }
            };
            clang::SourceRange defaultRange;
            std::string spelling;
            llvm::raw_string_ostream out(spelling);
            if (const auto* type = llvm::dyn_cast<clang::TemplateTypeParmDecl>(parameter))
            {
                node["kind"]  = "type";
                node["depth"] = type->getDepth();
                node["index"] = type->getIndex();
                if (type->hasDefaultArgument())
                {
                    spelling     = type->getDefaultArgument().getAsString(policy);
                    defaultRange = type->getDefaultArgumentInfo()->getTypeLoc().getSourceRange();
                }
            }
            else if (const auto* value = llvm::dyn_cast<clang::NonTypeTemplateParmDecl>(parameter))
            {
                node["kind"]           = "non_type";
                node["depth"]          = value->getDepth();
                node["index"]          = value->getIndex();
                node["type_spelling"]  = value->getType().getAsString(policy);
                node["type_dependent"] = value->getType()->isDependentType();
                if (value->hasDefaultArgument())
                {
                    value->getDefaultArgument()->printPretty(out, nullptr, policy);
                    defaultRange = value->getDefaultArgument()->getSourceRange();
                }
            }
            else if (const auto* nested = llvm::dyn_cast<clang::TemplateTemplateParmDecl>(parameter))
            {
                node["kind"]       = "template";
                node["depth"]      = nested->getDepth();
                node["index"]      = nested->getIndex();
                node["parameters"] = parameters(nested->getTemplateParameters());
                if (nested->hasDefaultArgument())
                {
                    nested->getDefaultArgument().getArgument().print(policy, out, true);
                    defaultRange = nested->getDefaultArgument().getSourceRange();
                }
            }
            else
            {
                unsupported(parameter, "Unsupported template parameter kind");
                continue;
            }
            if (defaultRange.isValid())
            {
                node["default_spelling"] = std::move(spelling);
                node["default_source"]   = source(defaultRange);
            }
            if (node.get("source")->kind() == Value::Null
                || (defaultRange.isValid() && node.get("default_source")->kind() == Value::Null))
                unsupported(parameter, "Template parameters and defaults require physical source evidence");
            result.emplace_back(std::move(node));
        }
        return result;
    }
}
