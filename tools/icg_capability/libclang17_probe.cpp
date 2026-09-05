#include <clang-c/Index.h>

#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

namespace
{

    std::string take_string(CXString value)
    {
        const char* text   = clang_getCString(value);
        std::string result = text == nullptr ? "" : text;
        clang_disposeString(value);
        return result;
    }

    std::string spelling(CXCursor cursor) { return take_string(clang_getCursorSpelling(cursor)); }

    std::string escape_json(const std::string& value)
    {
        std::string result;
        for (unsigned char character : value)
        {
            switch (character)
            {
            case '\\':
                result += "\\\\";
                break;
            case '"':
                result += "\\\"";
                break;
            case '\n':
                result += "\\n";
                break;
            case '\r':
                result += "\\r";
                break;
            case '\t':
                result += "\\t";
                break;
            default:
                if (character < 0x20)
                {
                    static const char digits[]  = "0123456789abcdef";
                    result                     += "\\u00";
                    result                     += digits[character >> 4];
                    result                     += digits[character & 0x0f];
                }
                else
                {
                    result += static_cast<char>(character);
                }
            }
        }
        return result;
    }

    struct Observations
    {
            int diagnostics_errors      = 0;
            int base_specifiers         = 0;
            int virtual_base_specifiers = 0;
            std::vector<long long> base_offset_queries;
            int diamond_bases                   = 0;
            long long diamond_own_offset        = -1;
            int implicit_special_constructors   = 0;
            int deleted_default_constructors    = 0;
            int defaulted_default_constructors  = 0;
            int friend_declarations             = 0;
            int private_fields                  = 0;
            int partial_specializations         = 0;
            int box_cursor_template_arguments   = -1;
            int box_type_template_arguments     = -1;
            int box_first_argument_kind         = -1;
            int box_second_argument_kind        = -1;
            long long box_second_argument_value = -1;
            int pack_cursor_template_arguments  = -1;
            int pack_argument_kind              = -1;
            int fixed_bit_width                 = -1;
            int dependent_bit_width             = -1;
            int raw_comments                    = 0;
            int annotation_attributes           = 0;
            int abstract_records                = 0;
            int anonymous_records               = 0;
    };

    struct VisitContext
    {
            Observations& observations;
    };

    CXChildVisitResult visit(CXCursor cursor, CXCursor lexical_parent, CXClientData data)
    {
        auto& context           = *static_cast<VisitContext*>(data);
        auto& observations      = context.observations;
        const CXCursorKind kind = clang_getCursorKind(cursor);
        const std::string name  = spelling(cursor);
        std::string parent      = spelling(clang_getCursorSemanticParent(cursor));
        if (parent.empty())
        {
            parent = spelling(lexical_parent);
        }

        if (kind == CXCursor_CXXBaseSpecifier)
        {
            ++observations.base_specifiers;
            observations.virtual_base_specifiers += static_cast<int>(clang_isVirtualBase(cursor));
            observations.base_offset_queries.push_back(clang_Cursor_getOffsetOfField(cursor));
            if (parent == "Diamond")
            {
                ++observations.diamond_bases;
            }
        }
        else if (kind == CXCursor_FieldDecl)
        {
            if (parent == "Diamond" && name == "own")
            {
                observations.diamond_own_offset = clang_Cursor_getOffsetOfField(cursor);
            }
            if (parent == "FriendTarget" && name == "hidden" && clang_getCXXAccessSpecifier(cursor) == CX_CXXPrivate)
            {
                ++observations.private_fields;
            }
            if (parent == "Facts" && name == "fixed_bits")
            {
                observations.fixed_bit_width = clang_getFieldDeclBitWidth(cursor);
            }
            if (parent == "DependentBits" && name == "value")
            {
                observations.dependent_bit_width = clang_getFieldDeclBitWidth(cursor);
            }
            if (parent == "Facts" && name == "documented"
                && !take_string(clang_Cursor_getRawCommentText(cursor)).empty())
            {
                ++observations.raw_comments;
            }
        }
        else if (kind == CXCursor_Constructor)
        {
            if (parent == "ImplicitSpecial")
            {
                ++observations.implicit_special_constructors;
            }
            if (parent == "DeletedDefault" && clang_CXXConstructor_isDefaultConstructor(cursor)
                && clang_CXXMethod_isDeleted(cursor))
            {
                ++observations.deleted_default_constructors;
            }
            if (parent == "DefaultedDefault" && clang_CXXConstructor_isDefaultConstructor(cursor)
                && clang_CXXMethod_isDefaulted(cursor))
            {
                ++observations.defaulted_default_constructors;
            }
        }
        else if (kind == CXCursor_FriendDecl && parent == "FriendTarget")
        {
            ++observations.friend_declarations;
        }
        else if (kind == CXCursor_ClassTemplatePartialSpecialization && name == "Box")
        {
            ++observations.partial_specializations;
        }
        else if (kind == CXCursor_AnnotateAttr && name == "trick:io=io")
        {
            ++observations.annotation_attributes;
        }
        else if ((kind == CXCursor_StructDecl || kind == CXCursor_ClassDecl) && name == "Abstract"
                 && clang_CXXRecord_isAbstract(cursor))
        {
            ++observations.abstract_records;
        }
        else if ((kind == CXCursor_StructDecl || kind == CXCursor_UnionDecl) && clang_Cursor_isAnonymous(cursor))
        {
            ++observations.anonymous_records;
        }
        else if (kind == CXCursor_VarDecl && (name == "box_use" || name == "pack_use"))
        {
            const CXType type          = clang_getCursorType(cursor);
            CXCursor declaration       = clang_getTypeDeclaration(type);
            const int cursor_arguments = clang_Cursor_getNumTemplateArguments(declaration);
            if (name == "box_use")
            {
                observations.box_cursor_template_arguments = cursor_arguments;
                observations.box_type_template_arguments   = clang_Type_getNumTemplateArguments(type);
                if (cursor_arguments >= 2)
                {
                    observations.box_first_argument_kind
                        = static_cast<int>(clang_Cursor_getTemplateArgumentKind(declaration, 0));
                    observations.box_second_argument_kind
                        = static_cast<int>(clang_Cursor_getTemplateArgumentKind(declaration, 1));
                    observations.box_second_argument_value = clang_Cursor_getTemplateArgumentValue(declaration, 1);
                }
            }
            else
            {
                observations.pack_cursor_template_arguments = cursor_arguments;
                if (cursor_arguments > 0)
                {
                    observations.pack_argument_kind
                        = static_cast<int>(clang_Cursor_getTemplateArgumentKind(declaration, 0));
                }
            }
        }

        clang_visitChildren(cursor, visit, data);
        return CXChildVisit_Continue;
    }

    void print_integer_array(const std::vector<long long>& values)
    {
        std::cout << '[';
        for (std::size_t index = 0; index < values.size(); ++index)
        {
            if (index != 0)
                std::cout << ',';
            std::cout << values[index];
        }
        std::cout << ']';
    }

} // namespace

int main(int argc, char** argv)
{
    if (argc != 2)
    {
        std::cerr << "usage: libclang17_probe FIXTURE\n";
        return 2;
    }

    CXIndex index = clang_createIndex(0, 0);
    if (index == nullptr)
    {
        std::cerr << "unable to create libclang index\n";
        return 2;
    }
    const char* arguments[]            = { "-x", "c++", "-std=c++17", "-fparse-all-comments" };
    CXTranslationUnit translation_unit = nullptr;
    const CXErrorCode error            = clang_parseTranslationUnit2(
        index, argv[1], arguments, 4, nullptr, 0,
        CXTranslationUnit_DetailedPreprocessingRecord | CXTranslationUnit_KeepGoing, &translation_unit);
    if (error != CXError_Success || translation_unit == nullptr)
    {
        std::cerr << "libclang parse failed with error " << static_cast<int>(error) << '\n';
        clang_disposeIndex(index);
        return 2;
    }

    Observations observations;
    const unsigned diagnostic_count = clang_getNumDiagnostics(translation_unit);
    for (unsigned index_value = 0; index_value < diagnostic_count; ++index_value)
    {
        CXDiagnostic diagnostic = clang_getDiagnostic(translation_unit, index_value);
        if (clang_getDiagnosticSeverity(diagnostic) >= CXDiagnostic_Error)
        {
            ++observations.diagnostics_errors;
        }
        clang_disposeDiagnostic(diagnostic);
    }
    VisitContext context { observations };
    clang_visitChildren(clang_getTranslationUnitCursor(translation_unit), visit, &context);

    std::cout << "{\n"
              << "  \"schema_version\": 1,\n"
              << "  \"frontend\": {\"api\": \"libclang-c\", \"version\": \""
              << escape_json(take_string(clang_getClangVersion())) << "\"},\n"
              << "  \"observations\": {\n"
              << "    \"abstract_records\": " << observations.abstract_records << ",\n"
              << "    \"annotation_attributes\": " << observations.annotation_attributes << ",\n"
              << "    \"anonymous_records\": " << observations.anonymous_records << ",\n"
              << "    \"base_offset_queries\": ";
    print_integer_array(observations.base_offset_queries);
    std::cout << ",\n"
              << "    \"base_specifiers\": " << observations.base_specifiers << ",\n"
              << "    \"box_cursor_template_arguments\": " << observations.box_cursor_template_arguments << ",\n"
              << "    \"box_first_argument_kind\": " << observations.box_first_argument_kind << ",\n"
              << "    \"box_second_argument_kind\": " << observations.box_second_argument_kind << ",\n"
              << "    \"box_second_argument_value\": " << observations.box_second_argument_value << ",\n"
              << "    \"box_type_template_arguments\": " << observations.box_type_template_arguments << ",\n"
              << "    \"defaulted_default_constructors\": " << observations.defaulted_default_constructors << ",\n"
              << "    \"deleted_default_constructors\": " << observations.deleted_default_constructors << ",\n"
              << "    \"dependent_bit_width\": " << observations.dependent_bit_width << ",\n"
              << "    \"diagnostics_errors\": " << observations.diagnostics_errors << ",\n"
              << "    \"diamond_bases\": " << observations.diamond_bases << ",\n"
              << "    \"diamond_own_offset\": " << observations.diamond_own_offset << ",\n"
              << "    \"fixed_bit_width\": " << observations.fixed_bit_width << ",\n"
              << "    \"friend_declarations\": " << observations.friend_declarations << ",\n"
              << "    \"implicit_special_constructors\": " << observations.implicit_special_constructors << ",\n"
              << "    \"pack_argument_kind\": " << observations.pack_argument_kind << ",\n"
              << "    \"pack_cursor_template_arguments\": " << observations.pack_cursor_template_arguments << ",\n"
              << "    \"partial_specializations\": " << observations.partial_specializations << ",\n"
              << "    \"private_fields\": " << observations.private_fields << ",\n"
              << "    \"raw_comments\": " << observations.raw_comments << ",\n"
              << "    \"virtual_base_specifiers\": " << observations.virtual_base_specifiers << "\n"
              << "  }\n"
              << "}\n";

    clang_disposeTranslationUnit(translation_unit);
    clang_disposeIndex(index);
    return observations.diagnostics_errors == 0 ? 0 : 1;
}
