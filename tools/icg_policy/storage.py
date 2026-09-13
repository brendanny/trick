"""Bounded builtin/enum, fixed-array and unsigned-bitfield storage decisions."""

from __future__ import annotations

from tools.icg_policy import enums
from tools.icg_policy.rules import PolicyError

KINDS = {
    "bool": "TRICK_BOOLEAN",
    "char": "TRICK_CHARACTER",
    "float": "TRICK_FLOAT",
    "int": "TRICK_INTEGER",
    "unsigned int": "TRICK_UNSIGNED_INTEGER",
    "long": "TRICK_LONG",
    "double": "TRICK_DOUBLE",
    "signed char": "TRICK_CHARACTER",
    "unsigned char": "TRICK_UNSIGNED_CHARACTER",
    "short": "TRICK_SHORT",
    "unsigned short": "TRICK_UNSIGNED_SHORT",
    "unsigned long": "TRICK_UNSIGNED_LONG",
    "long long": "TRICK_LONG_LONG",
    "unsigned long long": "TRICK_UNSIGNED_LONG_LONG",
    "char16_t": "TRICK_UNSIGNED_SHORT",
}


def resolve(field: dict, types: dict, declarations: dict | None = None) -> dict:
    # Canonical IDs expand aliases structurally, including aliases of arrays.
    node = types[types[field["type_id"]]["canonical_id"]]
    dimensions = []
    while node["kind"] == "array":
        extent = node["extent"]
        if extent is None or not 1 <= int(extent) <= 2147483647:
            raise PolicyError(
                "ICG_POLICY_ARRAY_EXTENT",
                f"fixed array extent must fit a positive INDEX.int: {field['qualified_name']}",
            )
        dimensions.append(int(extent))
        if len(dimensions) > 8:
            raise PolicyError(
                "ICG_POLICY_ARRAY_RANK", "fixed array exceeds TRICK_MAX_INDEX (8)"
            )
        node = types[types[node["element_id"]]["canonical_id"]]
    if (
        not (
            node["kind"] == "builtin"
            and node["spelling"] in KINDS
            or node["kind"] == "enum"
            and declarations is not None
        )
        or any(node["qualifiers"].values())
        or not field["name"]
    ):
        raise PolicyError(
            "ICG_POLICY_TYPE",
            f"required field outside unqualified scalar/array profile: {field['qualified_name']}",
        )
    # Lifecycle callers omit declarations and keep their characterized builtin
    # storage boundary. Enum metadata does not imply enum lifecycle support.
    if node["kind"] == "enum":
        if field["bitfield"]:
            raise PolicyError("ICG_POLICY_TYPE", "enum bitfields are not characterized")
        enum_id = node["declaration_id"]
        name = enums.storage_type(declarations[enum_id], declarations, types)
        return dict(
            element_type_id=node["id"],
            enum_id=enum_id,
            type_name=name,
            cpp_type=name + "".join(f"[{extent}]" for extent in dimensions),
            trick_type="TRICK_ENUMERATED",
            dimensions=dimensions,
        )
    name = node["spelling"]
    if field["bitfield"] and (dimensions or name != "unsigned int"):
        raise PolicyError(
            "ICG_POLICY_TYPE", "only unsigned int bitfields are characterized"
        )
    return dict(
        element_type_id=node["id"],
        type_name=name,
        cpp_type=name + "".join(f"[{extent}]" for extent in dimensions),
        trick_type="TRICK_UNSIGNED_BITFIELD" if field["bitfield"] else KINDS[name],
        dimensions=dimensions,
    )
