#include "ClangCompat.hh"

#include <cstring>

int main()
{
#if CLANG_VERSION_MAJOR >= 18
    const auto invalid = clang::Linkage::Invalid;
    const auto none    = clang::Linkage::None;
#else
    // LLVM 17 has six values (0..5); 6 is representable but unassigned.
    const auto invalid = static_cast<clang::Linkage>(6);
    const auto none    = clang::NoLinkage;
#endif
    if (trick::icg::compat::linkage(invalid) != nullptr)
        return 1;
    const auto* value = trick::icg::compat::linkage(none);
    return !value || std::strcmp(value, "none") != 0;
}
