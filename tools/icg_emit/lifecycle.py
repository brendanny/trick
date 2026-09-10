"""Render already-resolved lifecycle operations against the existing C ABI."""

from __future__ import annotations

PREAMBLE = """
#include <cstdlib>
#include <new>
namespace trick_icg_lifecycle_detail {
template<class T, class = void> struct PlacementDefault : std::false_type {};
template<class T> struct PlacementDefault<T,
    std::void_t<decltype(::new (static_cast<void*>(nullptr)) T())>> : std::true_type {};
}
// Contract: positive counts, nonthrowing special members, matching ownership.
// calloc allocations require destruct + free; scalar new requires delete.
"""


def render(node: dict, decision: dict, name: str) -> str:
    rule = decision["lifecycle"]
    cpp = "::" + name
    checks = {
        f"std::is_pod<{cpp}>::value": node["pod"],
        f"std::is_abstract<{cpp}>::value": node["abstract"],
        f"trick_icg_lifecycle_detail::PlacementDefault<{cpp}>::value": rule[
            "default_placement"
        ],
        f"std::is_destructible<{cpp}>::value": rule["destructor"]["available"],
        f"std::has_virtual_destructor<{cpp}>::value": rule["destructor"]["virtual"],
    }
    chunks = [
        f'static_assert({expression} == {str(value).lower()}, "ICG lifecycle trait mismatch: {name}");\n'
        for expression, value in checks.items()
    ]
    chunks.append(
        f'static_assert(alignof({cpp}) <= alignof(std::max_align_t), "ICG lifecycle allocation alignment");\n'
        'extern "C" {\n'
    )
    allocation, destruction, deletion = (
        rule[key] for key in ("allocate", "destruct", "delete")
    )
    if allocation["action"] != "absent":
        chunks.append(
            f"void* {allocation['symbol']}(int num) {{\n"
            f"    using T = {cpp};\n"
            "    if (num <= 0) return nullptr;\n"
            "    void* storage = std::calloc(static_cast<size_t>(num), sizeof(T));\n"
            "    if (!storage) return nullptr;\n"
        )
        if allocation["action"] == "construct":
            chunks.append(
                "    for (int i = 0; i < num; ++i) {\n"
                "        ::new (static_cast<unsigned char*>(storage) + static_cast<size_t>(i) * sizeof(T)) T();\n"
                "    }\n"
            )
        chunks.append("    return storage;\n}\n")
    if destruction["action"] == "noop":
        chunks.append(f"void {destruction['symbol']}(void*, int) {{}}\n")
    elif destruction["action"] == "loop":
        chunks.append(
            f"void {destruction['symbol']}(void* address, int num) {{\n"
            f"    using T = {cpp};\n"
            "    for (int i = 0; i < num; ++i) {\n"
            "        auto* object = reinterpret_cast<T*>(static_cast<unsigned char*>(address) + static_cast<size_t>(i) * sizeof(T));\n"
            "        object->~T();\n"
            "    }\n}\n"
        )
    if deletion["action"] == "noop":
        chunks.append(f"void {deletion['symbol']}(void*) {{}}\n")
    elif deletion["action"] == "scalar":
        chunks.append(
            f"void {deletion['symbol']}(void* address) {{\n"
            f"    delete static_cast<{cpp}*>(address);\n}}\n"
        )
    chunks.append("}\n")
    return "".join(chunks)
