"""Characterized ENUM_ATTR labels and value limits; no frontend objects."""

from __future__ import annotations

import re

from tools.icg_policy.rules import PolicyError


def template_type(node: dict, declarations: dict, types: dict) -> str:
    """Bounded named enum storage for template arguments and member rows."""
    underlying = types[types[node["underlying_type_id"]]["canonical_id"]]
    if (
        node["origin"] != "user"
        or not node["definition"]
        or not node["complete"]
        or not node["enumerators"]
        or int(node["size_bits"]) != 32
        or underlying["spelling"] not in ("int", "unsigned int")
    ):
        raise PolicyError(
            "ICG_POLICY_ENUM_STORAGE",
            "template enum storage requires a defined, nonempty int/unsigned-int enum",
        )
    chain = [node]
    parent = declarations.get(node.get("semantic_parent_id"))
    while parent is not None:
        if parent["kind"] != "namespace" or parent["inline"]:
            raise PolicyError(
                "ICG_POLICY_ENUM_STORAGE",
                "template enums require global or named non-inline namespace scope",
            )
        chain.insert(0, parent)
        parent = declarations.get(parent.get("semantic_parent_id"))
    if any(not re.fullmatch(r"[A-Za-z_]\w*", n["name"], re.ASCII) for n in chain):
        raise PolicyError(
            "ICG_POLICY_ENUM_STORAGE", "template enum requires an ASCII name"
        )
    metadata(node, declarations, types)
    return "::".join(n["name"] for n in chain)


def metadata(node: dict, declarations: dict, types: dict) -> dict:
    scope = []
    parent = declarations.get(node.get("semantic_parent_id"))
    while parent is not None:
        scope.insert(0, parent["name"])
        parent = declarations.get(parent.get("semantic_parent_id"))
    width = int(node["size_bits"])
    if width not in (8, 16, 32, 64):
        raise PolicyError(
            "ICG_POLICY_ENUM_WIDTH",
            "enum storage outside the characterized integer widths",
        )
    underlying = types[types[node["underlying_type_id"]]["canonical_id"]]
    # bool occupies a byte but Clang's enumerator APSInt has only one bit.
    value_width = 1 if underlying["spelling"] == "bool" else width
    rows = []
    for index, item in enumerate(node["enumerators"]):
        if not re.fullmatch(r"[A-Za-z_]\w*", item["name"], re.ASCII):
            raise PolicyError(
                "ICG_POLICY_NAME", "enumerator outside the ASCII ABI profile"
            )
        value = int(item["value"])
        if not -(2**31) <= value < 2**31:
            raise PolicyError(
                "ICG_POLICY_ENUM_VALUE",
                f"ENUM_ATTR.int cannot represent {node['qualified_name']}::{item['name']} = {value}",
            )
        # EnumVisitor::getSExtValue sign-extends even an unsigned narrow APSInt.
        # Do not claim old/new/native agreement when that changes its C++ value.
        if not node["underlying_signed"] and value >= 2 ** (value_width - 1):
            raise PolicyError(
                "ICG_POLICY_ENUM_SIGN_EXTENSION",
                f"legacy metadata encodes {node['qualified_name']}::{item['name']} = {value} as {value - 2**value_width}",
            )
        rows.append(
            dict(
                source_index=index,
                label="::".join([*scope, item["name"]]),
                cpp_name="::".join([*scope, node["name"], item["name"]]),
                value=item["value"],
            )
        )
    return dict(
        label_rule="LEGACY_CONTAINER_SCOPE",
        diagnostics=["LEGACY_SCOPED_LABEL_OMITS_ENUM"] if node["scoped"] else [],
        mods=0 if node["underlying_signed"] else 0x40000000,
        rows=rows,
    )
