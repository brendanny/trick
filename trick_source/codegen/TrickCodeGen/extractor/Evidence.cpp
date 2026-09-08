#include "Evidence.hh"

namespace trick::icg
{
    llvm::json::Object DeclarationHeader::json() const
    {
        return llvm::json::Object {
            { "id",                       id                                                                },
            { "kind",                     kind                                                              },
            { "name",                     name                                                              },
            { "qualified_name",           qualifiedName                                                     },
            { "usr",                      usr.empty() ? llvm::json::Value(nullptr) : llvm::json::Value(usr) },
            { "identity_kind",            fromSource ? "source" : "usr"                                     },
            { "source",                   llvm::json::Value(source)                                         },
            { "access",                   access                                                            },
            { "origin",                   origin                                                            },
            { "definition",               true                                                              },
            { "canonical_declaration_id", id                                                                },
            { "annotations",              llvm::json::Array(annotations)                                    },
            { "capabilities",             llvm::json::Array { }                                             }
        };
    }

    llvm::json::Object FriendSignature::json() const
    {
        llvm::json::Array parameters;
        for (const auto& parameter : parameterTypeUSRs)
            parameters.emplace_back(parameter);
        return llvm::json::Object {
            { "return_type_usr",     returnTypeUSR         },
            { "parameter_type_usrs", std::move(parameters) },
            { "returns_void",        returnsVoid           },
            { "variadic",            variadic              },
            { "method",              method                },
            { "language_linkage",    languageLinkage       },
            { "noexcept",            exceptionSpec         },
            { "calling_convention",  "c"                   },
            { "const",               isConst               },
            { "volatile",            isVolatile            },
            { "ref_qualifier",       refQualifier          }
        };
    }

    llvm::json::Object FriendEvidence::json() const
    {
        return llvm::json::Object {
            { "target_kind",           targetKind                                                                    },
            { "target_usr",            targetUSR                                                                     },
            { "target_qualified_name", targetQualifiedName                                                           },
            { "source",                llvm::json::Value(source)                                                     },
            { "signature",             signature ? llvm::json::Value(signature->json()) : llvm::json::Value(nullptr) }
        };
    }
}
