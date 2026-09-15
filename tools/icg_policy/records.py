"""Bounded ordinary record pointees; no allocation or ownership policy."""

from __future__ import annotations

import re

from tools.icg_policy.rules import PolicyError


def storage_type(node: dict, declarations: dict) -> str:
    if (
        node["origin"] != "user"
        or not node["complete"]
        or not node["standard_layout"]
        or node["bases"]
        or node.get("primary_template_id")
        or node["record_tag"] == "union"
    ):
        raise PolicyError(
            "ICG_POLICY_RECORD_STORAGE",
            "record pointers require complete ordinary standard-layout structs/classes",
        )
    chain = [node]
    parent = declarations.get(node.get("semantic_parent_id"))
    while parent is not None:
        if parent["kind"] != "namespace" or parent["inline"]:
            raise PolicyError(
                "ICG_POLICY_RECORD_STORAGE",
                "record pointers require global or named non-inline namespace scope",
            )
        chain.insert(0, parent)
        parent = declarations.get(parent.get("semantic_parent_id"))
    if any(not re.fullmatch(r"[A-Za-z_]\w*", n["name"], re.ASCII) for n in chain):
        raise PolicyError(
            "ICG_POLICY_RECORD_STORAGE", "record pointers require ASCII names"
        )
    return "::".join(n["name"] for n in chain)
