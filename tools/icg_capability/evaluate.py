#!/usr/bin/env python3
"""Verify LLVM 17 observations and write the extractor API decision evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXPECTED = {
    "abstract_records": 1,
    "annotation_attributes": 1,
    "anonymous_records": 2,
    "base_offset_queries": [-1, -1, -1, -1],
    "base_specifiers": 4,
    "box_cursor_template_arguments": 2,
    "box_first_argument_kind": 1,  # CXTemplateArgumentKind_Type
    "box_second_argument_kind": 4,  # CXTemplateArgumentKind_Integral
    "box_second_argument_value": 4,
    "box_type_template_arguments": 2,
    "defaulted_default_constructors": 1,
    "deleted_default_constructors": 1,
    "dependent_bit_width": -1,
    "diagnostics_errors": 0,
    "diamond_bases": 2,
    "diamond_inherited_left": -5,  # CXTypeLayoutError_InvalidFieldName
    "diamond_inherited_root": -5,  # virtual base's inherited field
    "root_type_offset": 0,
    "fixed_bit_width": 3,
    "friend_declarations": 1,
    "implicit_special_constructors": 0,
    "pack_argument_kind": 8,  # CXTemplateArgumentKind_Pack
    "pack_cursor_template_arguments": 1,
    "partial_specializations": 1,
    "private_fields": 1,
    "raw_comments": 1,
    "virtual_base_specifiers": 2,
}


def capability(status: str, required: bool, evidence: str) -> dict:
    return {"evidence": evidence, "required": required, "status": status}


def evaluate(document: dict) -> dict:
    if document.get("schema_version") != 1:
        raise ValueError("unsupported observation schema")
    frontend = document.get("frontend", {})
    if frontend.get("api") != "libclang-c" or "17.0." not in frontend.get(
        "version", ""
    ):
        raise ValueError(f"expected libclang 17.0.x, got {frontend!r}")
    observations = document.get("observations")
    if not isinstance(observations, dict):
        raise TypeError("missing observations")
    for name, expected in EXPECTED.items():
        actual = observations.get(name)
        if actual != expected:
            raise ValueError(
                f"unexpected {name}: expected {expected!r}, got {actual!r}"
            )
    if set(observations) != set(EXPECTED) | {
        "diamond_own_offset",
        "diamond_type_own_offset",
    }:
        raise ValueError("unexpected observation keys")
    if observations["diamond_own_offset"] < 0:
        raise ValueError("ordinary field-offset control query failed")
    if observations["diamond_type_own_offset"] != observations["diamond_own_offset"]:
        raise ValueError("type and cursor field-offset controls disagree")

    capabilities = {
        "abstract_record_detection": capability(
            "supported", True, "clang_CXXRecord_isAbstract identified Abstract"
        ),
        "annotations_and_comments": capability(
            "supported",
            True,
            "annotate attributes and raw field comments were both retained",
        ),
        "base_discovery_and_virtuality": capability(
            "supported",
            True,
            "four base specifiers were visited and both virtual bases were identified",
        ),
        "base_layout": capability(
            "unsupported",
            True,
            "clang_Type_getOffsetOf(Diamond, left/root) returned -5 (InvalidFieldName) for ordinary/virtual inherited fields; direct-field type and cursor controls agreed, and Root.root returned 0. Base cursors also returned -1 from the field-only cursor API, as expected",
        ),
        "dependent_bitfield_width": capability(
            "negative-query-supported",
            True,
            "dependent width returned -1 and fixed width returned 3; policy must preserve the unknown state",
        ),
        "explicit_special_members": capability(
            "supported",
            True,
            "explicitly deleted and explicitly defaulted default constructors were distinguished",
        ),
        "friend_and_access_discovery": capability(
            "supported",
            True,
            "friend declaration and private field access were both exposed",
        ),
        "implicit_special_members": capability(
            "unsupported",
            True,
            "the record requiring an implicit default constructor had no constructor cursor",
        ),
        "record_and_field_layout": capability(
            "supported",
            True,
            "record fields, anonymous records, a fixed bitfield, and a nonnegative field offset were exposed",
        ),
        "template_specializations": capability(
            "supported",
            True,
            "partial specialization plus type and integral arguments were exposed structurally",
        ),
        "variadic_pack_elements": capability(
            "unsupported",
            True,
            "Pack<int, double> was exposed as one opaque CXTemplateArgumentKind_Pack with no C API for its elements",
        ),
    }
    blockers = sorted(
        name
        for name, value in capabilities.items()
        if value["required"] and value["status"] == "unsupported"
    )
    return {
        "schema_version": 1,
        "decision": "libtooling",
        "frontend": frontend,
        "blockers": blockers,
        "capabilities": capabilities,
        "observations": observations,
    }


def stable_view(document: dict) -> dict:
    """Remove expected package/target variance before comparing a rerun."""
    result = json.loads(json.dumps(document))
    result["frontend"].pop("version", None)
    result["observations"].pop("diamond_own_offset", None)
    result["observations"].pop("diamond_type_own_offset", None)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observations", type=Path)
    parser.add_argument("--expected", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = evaluate(json.loads(args.observations.read_text()))
        encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.expected is not None:
            expected = json.loads(args.expected.read_text())
            if stable_view(expected) != stable_view(result):
                raise ValueError(f"result differs from {args.expected}")
        args.output.write_text(encoded)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"icg-capability: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
