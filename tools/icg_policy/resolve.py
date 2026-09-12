#!/usr/bin/env python3
"""Resolve validated facts into the versioned scalar legacy metadata policy."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.icg_policy import enums, lifecycle, rules, storage, templates  # noqa: E402
from tools.icg_schema import validate as ir  # noqa: E402

POLICY_VERSION = "scalar-metadata-11"
FACTS_SCHEMA = ROOT / "trick_source/codegen/TrickCodeGen/ir/extracted-facts.schema.json"
SCHEMA = Path(__file__).with_name("resolved.schema.json")
OUTPUTS = ["attributes", "enum-attributes"]
OUTPUT_PROFILES = [
    OUTPUTS,
    ["lifecycle"],
    [*OUTPUTS, "lifecycle"],
    ["template-attributes"],
]


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def model_digest(model: dict) -> str:
    return digest({key: value for key, value in model.items() if key != "digest"})


def request_for(
    facts: dict,
    *,
    outputs: list[str] | None = None,
    template_field_ids: list[str] | None = None,
) -> dict:
    return dict(
        file_ids=list(facts["provenance"]["selection"]["file_ids"]),
        outputs=list(OUTPUTS if outputs is None else outputs),
        offset_mode="numeric",
        policy_version=POLICY_VERSION,
        template_field_ids=list(template_field_ids or []),
    )


def validate_inputs(facts: dict, request: dict) -> None:
    ir.validate(json.loads(FACTS_SCHEMA.read_text()), facts)
    expected = request_for(facts)
    if (
        not isinstance(request, dict)
        or set(request) != set(expected)
        or request["outputs"] not in OUTPUT_PROFILES
        or request["offset_mode"] != "numeric"
        or request["policy_version"] != POLICY_VERSION
    ):
        raise rules.PolicyError("ICG_POLICY_REQUEST", "unsupported request contract")
    ids = request["file_ids"]
    if (
        not isinstance(ids, list)
        or not ids
        or any(not isinstance(i, str) for i in ids)
        or ids != sorted(set(ids))
        or not set(ids) <= set(expected["file_ids"])
    ):
        raise rules.PolicyError(
            "ICG_POLICY_REQUEST",
            "request exceeds captured selection or is empty/noncanonical",
        )
    fields = request["template_field_ids"]
    if (
        not isinstance(fields, list)
        or any(not isinstance(i, str) for i in fields)
        or fields != sorted(set(fields))
        or bool(fields) != (request["outputs"] == ["template-attributes"])
    ):
        raise rules.PolicyError(
            "ICG_POLICY_REQUEST",
            "template field IDs require an explicit, nonempty template-only request",
        )


def names(node: dict, declarations: dict) -> tuple[str, str]:
    # Context relationships use IDs. Names here are only the output ABI spelling.
    chain = [node]
    parent = declarations.get(node.get("semantic_parent_id"))
    while parent is not None:
        chain.insert(0, parent)
        parent = declarations.get(parent.get("semantic_parent_id"))
    if any(
        n["kind"] not in ("namespace", "record", "enum")
        or not re.fullmatch(r"[A-Za-z_]\w*", n["name"], re.ASCII)
        for n in chain
    ):
        raise rules.PolicyError(
            "ICG_POLICY_NAME", f"unsupported output name: {node['qualified_name']}"
        )
    symbol = "__".join(n["name"] for n in chain)
    namespaces = "::".join(n["name"] for n in chain if n["kind"] == "namespace")
    return symbol, (namespaces + "::" if namespaces else "") + "init_attr" + symbol


def access(record: dict, field: dict, init_function: str) -> dict:
    matching = []
    legacy_prefix = []
    for index, friend in enumerate(record["friends"]):
        if friend["target_kind"] != "function":
            continue
        signature = friend["signature"]
        if (
            friend["target_qualified_name"]
            .rsplit("::", 1)[-1]
            .startswith(init_function.rsplit("::", 1)[-1])
        ):
            legacy_prefix.append(index)
        if (
            friend["target_qualified_name"] == init_function
            and signature["returns_void"]
            and not signature["parameter_type_usrs"]
            and not signature["variadic"]
            and not signature["method"]
            and signature["language_linkage"] == "c++"
            and signature["noexcept"] == "false"
            and signature["calling_convention"] == "c"
        ):
            matching.append(index)
    public = field["access"] == "public"
    return dict(
        operation="member-access-in-init-attributes",
        allowed=public or bool(matching),
        rule="PUBLIC_MEMBER"
        if public
        else "EXACT_INIT_FRIEND"
        if matching
        else "NO_ACCESS_GRANT",
        friend_indices=matching,
        legacy_prefix_indices=legacy_prefix,
        compatibility="LEGACY_PREFIX_IS_NOT_ACCESS"
        if set(legacy_prefix) - set(matching)
        else None,
    )


def units_key(record: dict, field: dict, declarations: dict) -> str:
    containers = []
    while record is not None:
        if record["kind"] == "record":
            containers.insert(0, record["name"])
        record = declarations.get(record.get("semantic_parent_id"))
    return "__".join(containers) + "_" + field["name"]


def _build(facts: dict, request: dict, effective: dict) -> dict:
    declarations = {n["id"]: n for n in facts["declarations"]}
    types = {n["id"]: n for n in facts["types"]}
    files = {n["id"]: n for n in facts["files"]}
    policies = {}
    for i in request["file_ids"]:
        try:
            policies[i] = rules.file_policy(files[i], effective)
        except rules.PolicyError as error:
            raise rules.PolicyError(
                error.code, f"{files[i]['path']['portable']}: {error.message}"
            ) from error
    roots = {
        r["declaration_id"]
        for r in facts["provenance"]["selection"]["roots"]
        if r["source"]["expansion"]["file_id"] in request["file_ids"]
    }
    decisions = {}
    symbols = {}
    unit_keys = {}

    def decide(node: dict) -> dict:
        identifier = node["id"]
        if identifier in decisions:
            return decisions[identifier]
        result = dict(
            declaration_id=identifier,
            decision="omit",
            rule="NOT_REQUESTED",
            source=node["source"],
            parent_id=node.get("semantic_parent_id"),
            metadata=None,
        )
        decisions[identifier] = result
        if request["outputs"] == ["template-attributes"]:
            result["rule"] = "OUTPUT_NOT_REQUESTED"
            return result
        parent = declarations.get(node.get("semantic_parent_id"))
        ancestor = node
        while (
            ancestor["id"] not in roots
            and ancestor.get("semantic_parent_id") in declarations
        ):
            ancestor = declarations[ancestor["semantic_parent_id"]]
        if ancestor["id"] not in roots:
            return result
        if node["kind"] not in ("record", "enum", "field", "class_template"):
            result["rule"] = "NOT_METADATA_DECLARATION"
            return result
        if (
            node["kind"] == "enum"
            and "enum-attributes" not in request["outputs"]
            or node["kind"] == "field"
            and "attributes" not in request["outputs"]
        ):
            result["rule"] = "OUTPUT_NOT_REQUESTED"
            return result
        file_id = node["source"]["spelling"]["file_id"]
        if file_id not in policies:
            raise rules.PolicyError(
                "ICG_POLICY_EVIDENCE",
                "selected descendant originates outside requested files",
            )
        policy = policies[file_id]
        if policy["excluded"]:
            result["rule"] = "FILE_EXCLUDED"
            return result
        if parent and parent["kind"] in ("record", "class_template"):
            if decide(parent)["decision"] == "omit":
                result["rule"] = "PARENT_OMITTED"
                return result
        if node["kind"] in ("record", "enum", "class_template"):
            ignored = set(policy["ignore_types"]) | set(effective["ignore_types"])
            if node["name"] in ignored or node["qualified_name"] in ignored:
                result["rule"] = "ICG_IGNORE_TYPES"
                return result
            if node["access"] in ("private", "protected"):
                result["rule"] = "INACCESSIBLE_NESTED_TYPE"
                return result
            if node["kind"] == "enum" and not node["name"]:
                if not node["qualified_name"].endswith("(anonymous enum)"):
                    raise rules.PolicyError(
                        "ICG_POLICY_TYPE",
                        "typedef-named anonymous enum policy is not characterized",
                    )
                result["rule"] = "UNNAMED_ENUM"
                return result
            if node["kind"] == "enum" and not node["definition"]:
                result["rule"] = "OPAQUE_ENUM_DECLARATION"
                return result
            if not node.get("complete", False):
                if node["kind"] == "class_template":
                    raise rules.PolicyError(
                        "ICG_POLICY_TYPE",
                        "template metadata is outside this request profile",
                    )
                result["rule"] = "INCOMPLETE_TYPE"
                return result
            if node["kind"] == "record" and (
                node["bases"] or node.get("primary_template_id")
            ):
                raise rules.PolicyError(
                    "ICG_POLICY_TYPE",
                    "inheritance/template metadata is outside this request profile",
                )
            symbol, init_function = names(node, declarations)
            # Records and enums share the io_src_sizeof_<symbol> C namespace.
            key = symbol
            if key in symbols and symbols[key] != identifier:
                raise rules.PolicyError(
                    "ICG_POLICY_NAME", f"legacy symbol collision: {symbol}"
                )
            symbols[key] = identifier
            result.update(
                decision="include",
                rule="REQUESTED_METADATA",
                metadata=dict(
                    symbol=symbol,
                    init_function=init_function if node["kind"] == "record" else None,
                ),
            )
            if node["kind"] == "enum":
                result["metadata"]["enum"] = enums.metadata(node, declarations, types)
            else:
                result["metadata"]["lifecycle"] = (
                    lifecycle.resolve(node, declarations, types, symbol)
                    if "lifecycle" in request["outputs"]
                    else None
                )
        else:
            if not parent or parent["kind"] != "record":
                raise rules.PolicyError(
                    "ICG_POLICY_EVIDENCE", "field has no record owner"
                )
            if node["source"]["macro_expansion"]:
                raise rules.PolicyError(
                    "ICG_POLICY_EVIDENCE",
                    "macro field comment association is not characterized",
                )
            comment_index = None
            if not policy["no_comment"]:
                comment_index = rules.line_comments(files[file_id]).get(
                    node["source"]["end"]["line"]
                )
            payload = (
                files[file_id]["comments"][comment_index]["payload"]
                if comment_index is not None
                else None
            )
            try:
                annotation = rules.annotation(payload)
            except rules.PolicyError as error:
                raise rules.PolicyError(
                    error.code,
                    f"{files[file_id]['path']['portable']}:{node['source']['end']['line']} ({node['qualified_name']}): {error.message}",
                ) from error
            permitted = access(
                parent, node, decide(parent)["metadata"]["init_function"]
            )
            result["metadata"] = dict(
                type_id=node["type_id"],
                comment_index=comment_index,
                annotation=annotation,
                access=permitted,
                storage=None,
                units_map_key=units_key(parent, node, declarations),
            )
            if annotation["io"] == 0:
                result["rule"] = "IO_DISABLED"
                return result
            result["metadata"]["storage"] = storage.resolve(node, types)
            key = result["metadata"]["units_map_key"]
            if key in unit_keys and unit_keys[key] != identifier:
                raise rules.PolicyError(
                    "ICG_POLICY_NAME", f"legacy UnitsMap key collision: {key}"
                )
            unit_keys[key] = identifier
            # Literal numeric metadata does not perform a C++ member access.
            result.update(decision="include", rule="NUMERIC_OFFSET_METADATA")
        return result

    for node in facts["declarations"]:
        decide(node)
    identity = dict(
        facts_digest=digest(facts),
        request=request,
        settings=effective,
        policy_version=POLICY_VERSION,
    )
    model = dict(
        schema_version=11,
        kind="legacy-metadata-policy",
        policy_version=POLICY_VERSION,
        facts=dict(
            schema_version=facts["schema_version"],
            document_digest=digest(facts),
            input_digest=facts["provenance"]["input_digest"],
            graph_digest=facts["provenance"]["graph_digest"],
        ),
        request=deepcopy(request),
        settings=effective,
        input_digest=digest(identity),
        files=[policies[i] for i in sorted(policies)],
        declarations=[decisions[i] for i in sorted(decisions)],
        template_instances=templates.resolve(facts, request, effective, policies)
        if request["outputs"] == ["template-attributes"]
        else [],
    )
    model["digest"] = model_digest(model)
    return model


def resolve(facts: dict, request: dict) -> dict:
    validate_inputs(facts, request)
    model = _build(facts, request, rules.settings(facts))
    Draft202012Validator(json.loads(SCHEMA.read_text())).validate(model)
    return model


def validate(facts: dict, request: dict, model: dict) -> None:
    """Require the caller's request, valid facts, and exact versioned policy replay.

    The JSON schema independently checks structure; replay checks rule/evidence
    consistency before digest comparison. This is not an independent policy parser.
    Path settings are re-observed, so a changed/missing symlink requires re-resolution.
    """
    Draft202012Validator(json.loads(SCHEMA.read_text())).validate(model)
    validate_inputs(facts, request)
    expected = _build(facts, request, rules.settings(facts))
    if {k: v for k, v in model.items() if k != "digest"} != {
        k: v for k, v in expected.items() if k != "digest"
    }:
        raise rules.PolicyError(
            "ICG_POLICY_CONSISTENCY",
            "resolved decisions/evidence differ from the requested policy",
        )
    if model["digest"] != model_digest(model):
        raise rules.PolicyError("ICG_POLICY_DIGEST", "resolved model digest differs")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("facts", type=Path)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument(
        "--validate",
        type=Path,
        help="validate an existing model against facts and request",
    )
    args = parser.parse_args()
    try:
        facts = json.loads(args.facts.read_text(encoding="utf-8"))
        request = json.loads(args.request.read_text(encoding="utf-8"))
        if args.validate:
            validate(
                facts, request, json.loads(args.validate.read_text(encoding="utf-8"))
            )
        else:
            result = resolve(facts, request)
            print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
    except (ValueError, OSError, ValidationError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
