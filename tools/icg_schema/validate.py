#!/usr/bin/env python3
"""Validate an extracted-facts document against its schema and graph invariants."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, SchemaError, ValidationError

SPECIAL_MEMBERS = (
    "default_constructor",
    "copy_constructor",
    "move_constructor",
    "copy_assignment",
    "move_assignment",
    "destructor",
)


def graph_digest(document: dict) -> str:
    """Version 1: exact graph facts with only file spelled/real paths omitted.

    This is an output-equivalence fingerprint, not a parse cache key or a claim
    that different targets/frontends must produce identical facts.
    """
    graph = {
        "schema_version": document["schema_version"],
        "identity_version": document["provenance"]["identity_version"],
        "graph_digest_version": document["provenance"]["graph_digest_version"],
        **{
            key: sorted(copy.deepcopy(document[key]), key=lambda node: node["id"])
            for key in ("files", "types", "declarations")
        },
    }
    for node in graph["files"]:
        del node["path"]["spelled"]
        del node["path"]["real"]
    encoded = json.dumps(
        graph, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_capabilities(node: dict) -> None:
    capabilities = node["capabilities"]
    names = [entry["name"] for entry in capabilities]
    if len(names) != len(set(names)):
        raise ValueError(f"{node['id']} has duplicate capability names")
    by_name = {entry["name"]: entry for entry in capabilities}
    # Known reason codes have prerequisites even under a mislabeled capability.
    for entry in capabilities:
        if entry["reason_code"] == "BITFIELD_NOT_ADDRESSABLE" and (
            node["kind"] != "field"
            or not node.get("bitfield")
            or entry["name"] != "field-address"
        ):
            raise ValueError(
                f"{node['id']} BITFIELD_NOT_ADDRESSABLE requires a bitfield field-address capability"
            )
        if entry["name"] == "frontend-record-layout" and node["kind"] != "record":
            raise ValueError(f"{node['id']} record-layout capability requires a record")
        if entry["name"] == "field-address" and node["kind"] != "field":
            raise ValueError(f"{node['id']} field-address capability requires a field")
        if (
            entry["name"] == "template-pattern"
            or entry["reason_code"] == "DEPENDENT_TEMPLATE_PATTERN"
        ) and (node["kind"] != "class_template" or entry["name"] != "template-pattern"):
            raise ValueError(
                f"{node['id']} dependent-pattern capability requires a class template"
            )
    if node["kind"] == "record":
        expected = (
            ("supported", "SUPPORTED")
            if node["complete"]
            else ("unknown", "INCOMPLETE_TYPE")
        )
        layout = by_name.get("frontend-record-layout")
        if layout is None or (layout["status"], layout["reason_code"]) != expected:
            raise ValueError(
                f"{node['id']} record-layout capability disagrees with completeness"
            )


def unique(nodes: list[dict], category: str) -> dict[str, dict]:
    result = {}
    for node in nodes:
        identifier = node["id"]
        if identifier in result:
            raise ValueError(f"duplicate {category} ID: {identifier}")
        result[identifier] = node
    return result


def require(identifier: str, values: dict, context: str) -> None:
    if identifier not in values:
        raise ValueError(f"dangling reference {identifier!r} from {context}")


def validate_graph(document: dict) -> None:
    files = unique(document["files"], "file")
    types = unique(document["types"], "type")
    declarations = unique(document["declarations"], "declaration")
    require(document["provenance"]["translation_unit"], files, "provenance")
    paths = set()
    for node in files.values():
        path = node["path"]
        require(path["root"], document["provenance"]["path_roots"], node["id"])
        if any(part in ("", ".", "..") for part in path["portable"].split("/")):
            raise ValueError(f"{node['id']} has a noncanonical portable path")
        identity = (path["root"], path["portable"])
        if identity in paths:
            raise ValueError(f"duplicate rooted file path: {identity}")
        paths.add(identity)

    # JSON Schema bounds numeric values. Strings also need a canonical threshold
    # so equivalent facts cannot alternate between numeric and string encodings.
    quantities = [*types.values(), *declarations.values()]
    for node in declarations.values():
        quantities.extend(node.get("bases", []))
        quantities.extend(node.get("virtual_base_offsets", []))
    for node in quantities:
        for field in (
            "extent",
            "size_bits",
            "alignment_bits",
            "offset_bits",
            "bit_width",
            "data_size_bits",
            "non_virtual_size_bits",
            "non_virtual_alignment_bits",
        ):
            value = node.get(field)
            if isinstance(value, str) and int(value) <= 9007199254740991:
                raise ValueError(f"{field} uses a string for a JSON-safe integer")

    def source(value: dict, context: str) -> None:
        for point in ("spelling", "expansion", "end"):
            require(value[point]["file_id"], files, f"{context}.{point}")

    selection = document["provenance"]["selection"]
    selected_files = selection["file_ids"]
    if selected_files != sorted(set(selected_files)):
        raise ValueError("selection files must be unique and sorted")
    for identifier in selected_files:
        require(identifier, files, "selection.file_ids")
    if selection["mode"] == "main-file" and selected_files != [
        document["provenance"]["translation_unit"]
    ]:
        raise ValueError("main-file selection must select the translation unit")
    selected_occurrences = set()
    for root in selection["roots"]:
        require(root["declaration_id"], declarations, "selection.roots")
        source(root["source"], "selection.roots")
        if root["source"]["expansion"]["file_id"] not in selected_files:
            raise ValueError("selection root is outside the requested files")
        if declarations[root["declaration_id"]]["kind"] not in {
            "record",
            "class_template",
            "enum",
            "alias",
            "callable",
            "namespace",
            "namespace_alias",
        }:
            raise ValueError("selection root is not a selectable declaration")
        key = json.dumps(root, sort_keys=True)
        if key in selected_occurrences:
            raise ValueError("duplicate selection root occurrence")
        selected_occurrences.add(key)

    type_references = ("canonical_id", "pointee_id", "element_id", "result_id")
    declaration_references = ("declaration_id",)
    for node in types.values():
        context = node["id"]
        for field in type_references:
            if field in node:
                require(node[field], types, f"{context}.{field}")
        for identifier in node.get("parameter_ids", []):
            require(identifier, types, f"{context}.parameter_ids")
        for field in declaration_references:
            if field in node:
                require(node[field], declarations, f"{context}.{field}")
        for argument in node.get("template_arguments", []):
            stack = [argument]
            while stack:
                value = stack.pop()
                if "type_id" in value:
                    require(value["type_id"], types, f"{context}.template_arguments")
                if "declaration_id" in value:
                    require(
                        value["declaration_id"],
                        declarations,
                        f"{context}.template_arguments",
                    )
                stack.extend(value.get("elements", []))

    declaration_links = (
        "semantic_parent_id",
        "lexical_parent_id",
        "canonical_declaration_id",
        "target_namespace_id",
    )
    type_links = ("type_id", "underlying_type_id", "return_type_id")
    for node in declarations.values():
        context = node["id"]
        source(node["source"], context)
        for key in ("primary_template_id", "instantiation_pattern_id"):
            if node.get(key) is not None:
                require(node[key], declarations, f"{context}.{key}")
        if node.get("point_of_instantiation") is not None:
            source(node["point_of_instantiation"], context)
        template_parameters = list(node.get("template_parameters", []))
        while template_parameters:
            parameter = template_parameters.pop()
            source(parameter["source"], context)
            if parameter["default_source"] is not None:
                source(parameter["default_source"], context)
            template_parameters.extend(parameter["parameters"])
        arguments = list(node.get("template_arguments", [])) + list(
            node.get("instantiation_arguments") or []
        )
        while arguments:
            argument = arguments.pop()
            if "type_id" in argument:
                require(argument["type_id"], types, context)
            if "declaration_id" in argument:
                require(argument["declaration_id"], declarations, context)
            arguments.extend(argument.get("elements", []))
        for field in declaration_links:
            if field in node:
                require(node[field], declarations, f"{context}.{field}")
        for identifier in (
            node.get("field_ids", [])
            + node.get("nested_declaration_ids", [])
            + node.get("declaration_ids", [])
            + node.get("callable_ids", [])
            + node.get("overridden_declaration_ids", [])
            + node.get("overridden_implicit_destructor_record_ids", [])
        ):
            require(identifier, declarations, context)
        for reopening in node.get("reopening_sources", []):
            source(reopening, f"{context}.reopening_sources")
        for field in type_links:
            if field in node:
                if field != "return_type_id" or node[field] is not None:
                    require(node[field], types, f"{context}.{field}")
        for base in node.get("bases", []):
            require(base["declaration_id"], declarations, f"{context}.bases")
            require(base["type_id"], types, f"{context}.bases")
            source(base["source"], f"{context}.bases")
        for base in node.get("virtual_base_offsets", []):
            require(
                base["declaration_id"], declarations, f"{context}.virtual_base_offsets"
            )
        parameter_lists = [node.get("parameters", [])]
        for occurrence in node.get("redeclarations", []):
            source(occurrence["source"], f"{context}.redeclarations")
            if "lexical_parent_id" in occurrence:
                require(occurrence["lexical_parent_id"], declarations, context)
            for annotation in occurrence["annotations"]:
                source(annotation["source"], f"{context}.redeclarations.annotations")
            parameter_lists.append(occurrence["parameters"])
        for parameters in parameter_lists:
            for parameter in parameters:
                require(parameter["type_id"], types, f"{context}.parameters")
                require(parameter["original_type_id"], types, f"{context}.parameters")
                source(parameter["source"], f"{context}.parameters")
                if parameter["default_source"] is not None:
                    source(parameter["default_source"], f"{context}.parameters.default")
                for annotation in parameter["annotations"]:
                    source(annotation["source"], f"{context}.parameters.annotations")
        for member in node.get("special_members", []):
            for identifier in member["declaration_ids"]:
                require(identifier, declarations, f"{context}.special_members")
        for annotation in node["annotations"]:
            source(annotation["source"], f"{context}.annotations")

    for file in files.values():
        previous_end = -1
        for comment in file["comments"]:
            location = comment["source"]
            source(location, f"{file['id']}.comments")
            begin, end = location["spelling"], location["end"]
            payload = comment["payload"]
            # Translation-phase line splices may split a physical delimiter.
            # Keep the payload untouched; normalize only this lexical check.
            logical = re.sub(r"\\[ \t\v\f]*(?:\r\n|\r|\n)", "", payload)
            if (
                any(
                    location[key]["file_id"] != file["id"]
                    for key in ("spelling", "expansion", "end")
                )
                or location["macro_expansion"]
                or begin != location["expansion"]
                or end["offset"] - begin["offset"] != len(payload.encode("utf-8"))
                or begin["offset"] < previous_end
                or not (
                    logical.startswith("//")
                    or (logical.startswith("/*") and logical.endswith("*/"))
                )
            ):
                raise ValueError(
                    "raw comment has invalid physical span, bytes, or ordering"
                )
            previous_end = end["offset"]
        for include in file["includes"]:
            require(include["file_id"], files, f"{file['id']}.includes")
            source(include["source"], f"{file['id']}.includes")
    for index, diagnostic in enumerate(document["diagnostics"]):
        if diagnostic["source"] is not None:
            source(diagnostic["source"], f"diagnostics[{index}]")

    for node in declarations.values():
        if "friends" in node and node["kind"] != "record":
            raise ValueError("friend evidence requires a record owner")
        if node["kind"] == "record":
            if "friends" not in node:
                raise ValueError("record requires friend evidence")
            if not node.get("complete") and node["friends"]:
                raise ValueError("incomplete record cannot contain friend declarations")
        for friend in node.get("friends", []):
            source(friend["source"], f"{node['id']}.friends")
            signature = friend["signature"]
            # A target may intentionally be outside the extraction closure.
            # Cross-check any matching published declaration without requiring
            # traversal of an unrelated friend's implementation.
            for target in declarations.values():
                if target["usr"] != friend["target_usr"]:
                    continue
                if friend["target_kind"] == "record":
                    if target["kind"] not in ("record", "class_template"):
                        raise ValueError(
                            "friend target kind disagrees with its declaration"
                        )
                elif target["kind"] != "callable":
                    raise ValueError(
                        "friend target kind disagrees with its declaration"
                    )
                else:
                    if (
                        not {
                            "return_type_id",
                            "parameters",
                            "variadic",
                            "language_linkage",
                            "callable_kind",
                            "noexcept",
                            "calling_convention",
                            "const",
                            "volatile",
                            "ref_qualifier",
                        }
                        <= target.keys()
                    ):
                        raise ValueError("friend target is missing callable facts")
                    result = types.get(target["return_type_id"])
                    canonical = types[result["canonical_id"]] if result else None
                    if (
                        len(signature["parameter_type_usrs"])
                        != len(target["parameters"])
                        or signature["returns_void"]
                        != bool(
                            target["callable_kind"] in ("constructor", "destructor")
                            or (
                                canonical
                                and canonical["kind"] == "builtin"
                                and canonical["spelling"] == "void"
                            )
                        )
                        or signature["variadic"] != target["variadic"]
                        or signature["language_linkage"] != target["language_linkage"]
                        or signature["method"]
                        != (target["callable_kind"] != "function")
                        or any(
                            signature[key] != target[key]
                            for key in (
                                "noexcept",
                                "calling_convention",
                                "const",
                                "volatile",
                                "ref_qualifier",
                            )
                        )
                    ):
                        raise ValueError(
                            "friend signature disagrees with its declaration"
                        )
        for enumerator in node.get("enumerators", []):
            source(enumerator["source"], f"{node['id']}.enumerators")
            for annotation in enumerator["annotations"]:
                source(annotation["source"], f"{node['id']}.enumerators.annotations")

    validate_structure(types, declarations)
    validate_templates(types, declarations)
    for node in declarations.values():
        validate_capabilities(node)


def validate_structure(types: dict[str, dict], declarations: dict[str, dict]) -> None:
    """Kind-aware rules for the implemented structural slice, not all future IR."""
    edges = {
        "declaration_id",
        "pointee_id",
        "element_id",
        "extent",
        "result_id",
        "parameter_ids",
        "template_arguments",
    }
    shapes = {
        "builtin": set(),
        "record": {"declaration_id"},
        "enum": {"declaration_id"},
        "alias": {"declaration_id"},
        "pointer": {"pointee_id"},
        "lvalue_reference": {"pointee_id"},
        "rvalue_reference": {"pointee_id"},
        "array": {"element_id", "extent"},
    }

    def need(node: dict, fields: set[str]) -> None:
        missing = fields - node.keys()
        if missing:
            raise ValueError(
                f"{node['id']} missing structural fields: {sorted(missing)}"
            )

    for node in types.values():
        kind = node["kind"]
        canonical = types[node["canonical_id"]]
        if canonical["canonical_id"] != canonical["id"]:
            raise ValueError(f"{node['id']} canonical target is not self-canonical")
        if kind in shapes:
            need(node, shapes[kind])
            extra = (node.keys() & edges) - shapes[kind]
            if extra:
                raise ValueError(
                    f"{node['id']} has invalid structural fields: {sorted(extra)}"
                )
            if canonical["kind"] == "alias" or (
                kind != "alias" and canonical["kind"] != kind
            ):
                raise ValueError(f"{node['id']} has an invalid canonical kind")
            if kind != "alias" and node["qualifiers"] != canonical["qualifiers"]:
                raise ValueError(f"{node['id']} has inconsistent canonical qualifiers")
        if (
            kind in ("record", "enum", "alias")
            and declarations[node["declaration_id"]]["kind"] != kind
        ):
            raise ValueError(f"{node['id']} points to the wrong declaration kind")
        if kind == "array" and any(node["qualifiers"].values()):
            raise ValueError(
                f"{node['id']} array qualifiers must be on the element type"
            )
        if kind in {"record", "enum"} and node["declaration_id"] != canonical.get(
            "declaration_id"
        ):
            raise ValueError(f"{node['id']} has inconsistent canonical {kind} identity")
        if kind in ("pointer", "lvalue_reference", "rvalue_reference") and types[
            node["pointee_id"]
        ]["canonical_id"] != canonical.get("pointee_id"):
            raise ValueError(f"{node['id']} has inconsistent canonical pointee")
        if kind == "array":
            if types[node["element_id"]]["canonical_id"] != canonical.get("element_id"):
                raise ValueError(f"{node['id']} has inconsistent canonical element")
            if node["extent"] != canonical.get("extent"):
                raise ValueError(f"{node['id']} has inconsistent canonical extent")

    def integer_type(identifier: str) -> dict:
        node = types[types[identifier]["canonical_id"]]
        name = " ".join(
            word
            for word in node["spelling"].split()
            if word not in {"const", "volatile", "restrict"}
        )
        if node["kind"] != "builtin" or name not in {
            "bool",
            "char",
            "signed char",
            "unsigned char",
            "wchar_t",
            "char16_t",
            "char32_t",
            "short",
            "unsigned short",
            "int",
            "unsigned int",
            "long",
            "unsigned long",
            "long long",
            "unsigned long long",
            "__int128",
            "unsigned __int128",
        }:
            raise ValueError(f"{identifier} is not a supported integral type")
        return node

    def parameter_key(identifier):
        canonical = types[types[identifier]["canonical_id"]]
        key = {
            k: v
            for k, v in canonical.items()
            if k not in {"id", "canonical_id", "qualifiers", "spelling"}
        }
        if canonical["kind"] == "builtin":
            key["spelling"] = " ".join(
                w
                for w in canonical["spelling"].split()
                if w not in {"const", "volatile", "restrict"}
            )
        return key

    for node in declarations.values():
        kind = node["kind"]
        if node["identity_kind"] == "usr" and not node["usr"]:
            raise ValueError(f"{node['id']} has no USR for its identity")
        if kind in {
            "record",
            "field",
            "enum",
            "alias",
            "namespace",
            "namespace_alias",
            "callable",
            "class_template",
        }:
            if node.get("canonical_declaration_id") != node["id"]:
                raise ValueError(f"{node['id']} is not a canonical declaration")
        for key in ("semantic_parent_id", "lexical_parent_id"):
            if key in node and declarations[node[key]]["kind"] not in {
                "record",
                "namespace",
            }:
                raise ValueError(f"{node['id']} has an invalid declaration context")
        parent = declarations.get(node.get("semantic_parent_id"))
        if parent:
            if (
                parent["identity_kind"] == "source"
                and node["identity_kind"] != "source"
            ):
                raise ValueError(
                    f"{node['id']} must inherit source identity from its context"
                )
            if parent["kind"] == "namespace" and node["id"] not in parent.get(
                "declaration_ids", []
            ):
                raise ValueError(f"{node['id']} has inconsistent namespace ownership")
            if (
                parent["kind"] == "record"
                and kind in {"record", "enum", "alias", "class_template"}
                and node["id"] not in parent.get("nested_declaration_ids", [])
            ):
                raise ValueError(
                    f"{node['id']} has inconsistent nested declaration ownership"
                )
        namespace_fields = {"inline", "declaration_ids", "reopening_sources"}
        if kind != "namespace" and namespace_fields & node.keys():
            raise ValueError(f"{node['id']} has namespace-only fields")
        if kind != "namespace_alias" and "target_namespace_id" in node:
            raise ValueError(f"{node['id']} has a namespace-alias-only field")
        enum_fields = {"scoped", "underlying_fixed", "underlying_signed", "enumerators"}
        record_layout_fields = {
            "data_size_bits",
            "non_virtual_size_bits",
            "non_virtual_alignment_bits",
        }
        if (
            kind != "record"
            and (record_layout_fields | {"bases", "virtual_base_offsets"}) & node.keys()
        ):
            raise ValueError(f"{node['id']} has record-only layout fields")
        if kind != "enum" and enum_fields & node.keys():
            raise ValueError(f"{node['id']} has enum-only fields")
        if kind != "record" and {"callable_ids", "special_members"} & node.keys():
            raise ValueError(f"{node['id']} has record-only callable fields")
        callable_fields = {
            "callable_kind",
            "special_member_kind",
            "return_type_id",
            "parameters",
            "const",
            "volatile",
            "ref_qualifier",
            "noexcept",
            "virtual",
            "pure",
            "final",
            "deleted",
            "defaulted",
            "explicit",
            "constexpr",
            "variadic",
            "user_provided",
            "calling_convention",
            "language_linkage",
            "linkage",
            "overridden_declaration_ids",
            "overridden_implicit_destructor_record_ids",
            "redeclarations",
        }
        if kind != "callable" and callable_fields & node.keys():
            raise ValueError(f"{node['id']} has callable-only fields")
        if kind == "callable":
            need(node, callable_fields | {"static"})
            if {
                "type_id",
                "underlying_type_id",
                "complete",
                "field_ids",
                "nested_declaration_ids",
                "size_bits",
                "alignment_bits",
                "offset_bits",
                "record_tag",
                "anonymous",
            } & node.keys():
                raise ValueError(f"{node['id']} callable claims type or layout facts")
            member = node["callable_kind"] != "function"
            if member != bool(parent and parent["kind"] == "record"):
                raise ValueError(f"{node['id']} has inconsistent callable context")
            if member and node["id"] not in parent.get("callable_ids", []):
                raise ValueError(f"{node['id']} has inconsistent callable ownership")
            if member and node["language_linkage"] == "c":
                raise ValueError(
                    f"{node['id']} member callable cannot have C language linkage"
                )
            if (node["access"] == "none") == member:
                raise ValueError(f"{node['id']} has inconsistent callable access")
            no_return = node["callable_kind"] in {"constructor", "destructor"}
            if (node["return_type_id"] is None) != no_return:
                raise ValueError(f"{node['id']} has inconsistent callable return type")
            if (not member or node["static"]) and (
                node["const"]
                or node["volatile"]
                or node["ref_qualifier"] != "none"
                or node["virtual"]
                or node["pure"]
                or node["final"]
            ):
                raise ValueError(f"{node['id']} has invalid instance-method flags")
            if node["static"] and node["callable_kind"] not in {"method", "function"}:
                raise ValueError(f"{node['id']} has invalid static callable kind")
            if not member and node["static"] and node["linkage"] != "internal":
                raise ValueError(
                    f"{node['id']} static function requires internal linkage"
                )
            if (
                node["linkage"] in {"internal", "unique_external"}
                and node["identity_kind"] != "source"
            ):
                raise ValueError(
                    f"{node['id']} translation-unit-local callable requires source identity"
                )
            if (
                node["pure"] or node["final"] or node["overridden_declaration_ids"]
            ) and not node["virtual"]:
                raise ValueError(f"{node['id']} virtual flags require virtual dispatch")
            if node["explicit"] and node["callable_kind"] not in {
                "constructor",
                "conversion",
            }:
                raise ValueError(f"{node['id']} has invalid explicit callable kind")
            if node["callable_kind"] == "constructor" and (
                node["virtual"]
                or node["const"]
                or node["volatile"]
                or node["ref_qualifier"] != "none"
            ):
                raise ValueError(f"{node['id']} has invalid constructor flags")
            if node["callable_kind"] in {"destructor", "conversion"} and (
                node["parameters"] or node["variadic"]
            ):
                raise ValueError(
                    f"{node['id']} destructor/conversion cannot have parameters"
                )
            special = node["special_member_kind"]
            if special != "none":
                expected_kind = (
                    "constructor"
                    if special.endswith("constructor")
                    else "destructor"
                    if special == "destructor"
                    else "method"
                )
                if node["callable_kind"] != expected_kind or node["static"]:
                    raise ValueError(
                        f"{node['id']} has inconsistent special-member kind"
                    )
            elif node["defaulted"] or node["callable_kind"] == "destructor":
                raise ValueError(f"{node['id']} requires a special-member kind")
            if node["user_provided"] and node["deleted"]:
                raise ValueError(
                    f"{node['id']} deleted callable cannot be user-provided"
                )
            if (node["deleted"] or node["defaulted"]) and not node["definition"]:
                raise ValueError(
                    f"{node['id']} deleted/defaulted callable requires definition evidence"
                )
            if node["annotations"] != [
                a for r in node["redeclarations"] for a in r["annotations"]
            ]:
                raise ValueError(
                    f"{node['id']} has inconsistent callable annotation aggregation"
                )
            if node["definition"] != any(
                r["definition"] for r in node["redeclarations"]
            ):
                raise ValueError(
                    f"{node['id']} has inconsistent callable definition evidence"
                )
            if (
                node["parameters"] != node["redeclarations"][-1]["parameters"]
                or node["source"] != node["redeclarations"][-1]["source"]
            ):
                raise ValueError(
                    f"{node['id']} must use its last redeclaration evidence"
                )
            signature = [parameter_key(p["type_id"]) for p in node["parameters"]]
            for occurrence in node["redeclarations"]:
                if "lexical_parent_id" in occurrence and declarations[
                    occurrence["lexical_parent_id"]
                ]["kind"] not in {"namespace", "record"}:
                    raise ValueError(f"{node['id']} has invalid redeclaration context")
                # Parameter top-level CV does not participate in overload identity.
                if len(occurrence["parameters"]) != len(signature):
                    raise ValueError(
                        f"{node['id']} has inconsistent redeclaration arity"
                    )
                if [
                    parameter_key(p["type_id"]) for p in occurrence["parameters"]
                ] != signature:
                    raise ValueError(
                        f"{node['id']} has inconsistent redeclaration parameter types"
                    )
                for parameter in occurrence["parameters"]:
                    original = types[
                        types[parameter["original_type_id"]]["canonical_id"]
                    ]
                    adjusted = types[types[parameter["type_id"]]["canonical_id"]]
                    if original["kind"] == "array":
                        if (
                            adjusted["kind"] != "pointer"
                            or adjusted["pointee_id"] != original["element_id"]
                        ):
                            raise ValueError(
                                f"{node['id']} has inconsistent adjusted array parameter"
                            )
                    elif parameter_key(parameter["original_type_id"]) != parameter_key(
                        parameter["type_id"]
                    ):
                        raise ValueError(
                            f"{node['id']} has inconsistent original parameter type"
                        )
                    if parameter["has_default"] != (
                        parameter["default_origin"] is not None
                        and parameter["default_source"] is not None
                        and parameter["default_spelling"] is not None
                    ):
                        raise ValueError(
                            f"{node['id']} has inconsistent default argument evidence"
                        )
                    if not parameter["has_default"] and (
                        parameter["default_origin"] is not None
                        or parameter["default_source"] is not None
                        or parameter["default_spelling"] is not None
                    ):
                        raise ValueError(
                            f"{node['id']} has spurious default argument evidence"
                        )
            for index in range(len(signature)):
                written = None
                for occurrence in node["redeclarations"]:
                    parameter = occurrence["parameters"][index]
                    evidence = (
                        parameter["default_spelling"],
                        parameter["default_source"],
                    )
                    if parameter["default_origin"] == "written":
                        if written is not None:
                            raise ValueError(
                                f"{node['id']} parameter default is written more than once"
                            )
                        written = evidence
                    elif parameter["default_origin"] == "inherited":
                        if written is None or evidence != written:
                            raise ValueError(
                                f"{node['id']} has inconsistent inherited default evidence"
                            )
                    elif written is not None:
                        raise ValueError(
                            f"{node['id']} loses an effective default on a later redeclaration"
                        )
            overrides = node["overridden_declaration_ids"]
            if overrides != sorted(set(overrides)):
                raise ValueError(f"{node['id']} overrides must be sorted and unique")
            for identifier in overrides:
                target = declarations[identifier]
                if (
                    identifier == node["id"]
                    or target["kind"] != "callable"
                    or not target.get("virtual")
                    or target.get("final")
                ):
                    raise ValueError(f"{node['id']} has invalid overridden callable")
            implicit_overrides = node["overridden_implicit_destructor_record_ids"]
            if implicit_overrides != sorted(set(implicit_overrides)):
                raise ValueError(
                    f"{node['id']} implicit overrides must be sorted and unique"
                )
            if implicit_overrides and (
                node["callable_kind"] != "destructor" or not node["virtual"]
            ):
                raise ValueError(
                    f"{node['id']} implicit overrides require a virtual destructor"
                )
            for identifier in implicit_overrides:
                target = declarations[identifier]
                slots = target.get("special_members", [])
                if target["kind"] != "record" or not any(
                    s["kind"] == "destructor"
                    and s["state"] == "implicit"
                    and s["virtual"]
                    for s in slots
                ):
                    raise ValueError(
                        f"{node['id']} has invalid implicit destructor override"
                    )
        if kind in {"record", "enum", "namespace"}:
            need(node, {"anonymous"})
            if node["anonymous"] != (node["name"] == ""):
                raise ValueError(f"{node['id']} has inconsistent anonymous naming")
            if node["anonymous"] and node["identity_kind"] != "source":
                raise ValueError(
                    f"{node['id']} anonymous declaration requires source identity"
                )
        if kind == "namespace":
            need(node, namespace_fields)
            if any(
                key in node
                for key in ("type_id", "field_ids", "size_bits", "offset_bits")
            ):
                raise ValueError(f"{node['id']} namespace claims type or layout facts")
            if node["declaration_ids"] != sorted(node["declaration_ids"]):
                raise ValueError(f"{node['id']} namespace members are not sorted")
            if node["source"] != node["reopening_sources"][0]:
                raise ValueError(
                    f"{node['id']} namespace source is not its first block"
                )
            for identifier in node["declaration_ids"]:
                member = declarations[identifier]
                if (
                    member.get("semantic_parent_id") != node["id"]
                    or member["kind"] == "field"
                ):
                    raise ValueError(f"{node['id']} has an invalid namespace member")
        if kind == "namespace_alias":
            need(node, {"target_namespace_id"})
            if declarations[node["target_namespace_id"]]["kind"] not in {
                "namespace",
                "namespace_alias",
            }:
                raise ValueError(f"{node['id']} has an invalid namespace alias target")
        if kind == "alias":
            need(node, {"type_id", "underlying_type_id"})
            alias = types[node["type_id"]]
            if alias["kind"] != "alias" or alias["declaration_id"] != node["id"]:
                raise ValueError(f"{node['id']} has an invalid alias type")
            if (
                alias["canonical_id"]
                != types[node["underlying_type_id"]]["canonical_id"]
            ):
                raise ValueError(f"{node['id']} has an inconsistent alias target")
        if kind == "enum":
            need(
                node,
                enum_fields
                | {
                    "type_id",
                    "underlying_type_id",
                    "complete",
                    "size_bits",
                    "alignment_bits",
                },
            )
            enum_type = types[node["type_id"]]
            if enum_type["kind"] != "enum" or enum_type["declaration_id"] != node["id"]:
                raise ValueError(f"{node['id']} has an invalid enum type")
            underlying = integer_type(node["underlying_type_id"])
            if any(underlying["qualifiers"].values()):
                raise ValueError(f"{node['id']} has a qualified enum underlying type")
            name = underlying["spelling"]
            # Plain char and wchar_t signedness is target-dependent. The other
            # supported integral builtin spellings have fixed signedness.
            if name not in {"char", "wchar_t"}:
                signed = not (
                    name.startswith("unsigned ")
                    or name in {"bool", "char16_t", "char32_t"}
                )
                if node["underlying_signed"] != signed:
                    raise ValueError(
                        f"{node['id']} has inconsistent underlying signedness"
                    )
            if (
                not node["complete"]
                or node["size_bits"] is None
                or node["alignment_bits"] is None
            ):
                raise ValueError(
                    f"{node['id']} enum requires a complete integral layout"
                )
            width = int(node["size_bits"])
            if width < 1 or int(node["alignment_bits"]) < 1:
                raise ValueError(f"{node['id']} enum has an invalid layout")
            if node["scoped"] and (not node["underlying_fixed"] or node["anonymous"]):
                raise ValueError(f"{node['id']} scoped enum must be named and fixed")
            if not node["definition"] and (
                not node["underlying_fixed"] or node["enumerators"]
            ):
                raise ValueError(
                    f"{node['id']} opaque enum must be fixed and have no enumerators"
                )
            names = [entry["name"] for entry in node["enumerators"]]
            if any(not name for name in names) or len(names) != len(set(names)):
                raise ValueError(
                    f"{node['id']} enum has empty or duplicate enumerator names"
                )
            for entry in node["enumerators"]:
                value = int(entry["value"])
                if node["underlying_signed"]:
                    fits = (value if value >= 0 else ~value).bit_length() < width
                else:
                    fits = value >= 0 and value.bit_length() <= width
                if not fits or (
                    underlying["spelling"] == "bool" and value not in (0, 1)
                ):
                    raise ValueError(
                        f"{node['id']} enumerator is outside its underlying range"
                    )
        if kind == "record":
            need(
                node,
                {
                    "type_id",
                    "complete",
                    "field_ids",
                    "nested_declaration_ids",
                    "callable_ids",
                    "special_members",
                    "bases",
                    "virtual_base_offsets",
                    "size_bits",
                    "alignment_bits",
                }
                | record_layout_fields,
            )
            record_type = types[node["type_id"]]
            if (
                record_type["kind"] != "record"
                or record_type["declaration_id"] != node["id"]
            ):
                raise ValueError(f"{node['id']} has an invalid record type")
            if not node["complete"] and (
                node["definition"]
                or node["field_ids"]
                or node.get("size_bits") is not None
                or node.get("alignment_bits") is not None
                or node["bases"]
                or node["virtual_base_offsets"]
                or node["callable_ids"]
                or any(node[key] is not None for key in record_layout_fields)
            ):
                raise ValueError(
                    f"{node['id']} incomplete record claims a definition or layout"
                )
            if node["complete"]:
                if not node["definition"] or any(
                    node[key] is None
                    for key in record_layout_fields | {"size_bits", "alignment_bits"}
                ):
                    raise ValueError(
                        f"{node['id']} complete record requires definition and layout"
                    )
                if (
                    int(node["data_size_bits"]) > int(node["size_bits"])
                    or int(node["non_virtual_size_bits"]) > int(node["size_bits"])
                    or int(node["alignment_bits"]) < 1
                    or int(node["non_virtual_alignment_bits"]) < 1
                ):
                    raise ValueError(
                        f"{node['id']} has inconsistent record layout sizes"
                    )
            if node.get("record_tag") == "union" and (
                node["bases"] or node["virtual_base_offsets"]
            ):
                raise ValueError(f"{node['id']} union cannot have bases")
            base_ids = [base["declaration_id"] for base in node["bases"]]
            if len(base_ids) != len(set(base_ids)):
                raise ValueError(f"{node['id']} has duplicate direct bases")
            for base in node["bases"]:
                target = declarations[base["declaration_id"]]
                canonical = types[types[base["type_id"]]["canonical_id"]]
                if (
                    target["kind"] != "record"
                    or not target.get("complete")
                    or target.get("record_tag") == "union"
                ):
                    raise ValueError(
                        f"{node['id']} base must be a complete non-union record"
                    )
                if (
                    canonical["kind"] != "record"
                    or canonical["declaration_id"] != target["id"]
                    or any(canonical["qualifiers"].values())
                ):
                    raise ValueError(
                        f"{node['id']} base type does not match its declaration"
                    )
                expected_access = base["written_access"]
                if expected_access == "none":
                    expected_access = (
                        "private" if node.get("record_tag") == "class" else "public"
                    )
                if base["access"] != expected_access:
                    raise ValueError(f"{node['id']} has inconsistent base access")
                if base["virtual"]:
                    if base["offset_bits"] is not None:
                        raise ValueError(
                            f"{node['id']} virtual edge must not claim a fixed offset"
                        )
                elif base["offset_bits"] is None or int(base["offset_bits"]) > int(
                    node["size_bits"]
                ):
                    raise ValueError(
                        f"{node['id']} nonvirtual base has an invalid offset"
                    )
            virtual_ids = [
                base["declaration_id"] for base in node["virtual_base_offsets"]
            ]
            if virtual_ids != sorted(set(virtual_ids)):
                raise ValueError(
                    f"{node['id']} virtual base offsets must be unique and sorted"
                )
            for base in node["virtual_base_offsets"]:
                target = declarations[base["declaration_id"]]
                if (
                    target["kind"] != "record"
                    or not target.get("complete")
                    or target.get("record_tag") == "union"
                ):
                    raise ValueError(
                        f"{node['id']} virtual base must be a complete non-union record"
                    )
                if base["offset_bits"] is None or int(base["offset_bits"]) > int(
                    node["size_bits"]
                ):
                    raise ValueError(
                        f"{node['id']} virtual base has an invalid complete-object offset"
                    )
            for field, expected in (
                ("field_ids", {"field"}),
                (
                    "nested_declaration_ids",
                    {"record", "alias", "enum", "class_template"},
                ),
                ("callable_ids", {"callable"}),
            ):
                ids = node[field]
                if len(ids) != len(set(ids)):
                    raise ValueError(f"{node['id']} has duplicate {field}")
                for identifier in ids:
                    member = declarations[identifier]
                    if (
                        member["kind"] not in expected
                        or member.get("semantic_parent_id") != node["id"]
                    ):
                        raise ValueError(
                            f"{node['id']} has an invalid member in {field}"
                        )
            if tuple(s["kind"] for s in node["special_members"]) != SPECIAL_MEMBERS:
                raise ValueError(
                    f"{node['id']} must list all six special-member kinds in order"
                )
            for slot in node["special_members"]:
                expected = sorted(
                    identifier
                    for identifier in node["callable_ids"]
                    if declarations[identifier].get("special_member_kind")
                    == slot["kind"]
                )
                if slot["declaration_ids"] != expected or (
                    slot["state"] == "user_declared"
                ) != bool(expected):
                    raise ValueError(
                        f"{node['id']} has inconsistent special-member declaration links"
                    )
                if (slot["state"] == "unknown") != (not node["complete"]):
                    raise ValueError(
                        f"{node['id']} has inconsistent special-member completeness"
                    )
                if slot["state"] == "implicit":
                    if (
                        slot["deleted"] is None
                        or slot["trivial"] is None
                        or slot["virtual"] is None
                        or slot["noexcept"] is None
                    ):
                        raise ValueError(
                            f"{node['id']} implicit special member requires frontend facts"
                        )
                elif any(
                    slot[key] is not None
                    for key in ("deleted", "trivial", "virtual", "noexcept")
                ):
                    raise ValueError(
                        f"{node['id']} nonimplicit special member claims implicit facts"
                    )
                if slot["virtual"] and slot["kind"] != "destructor":
                    raise ValueError(
                        f"{node['id']} only an implicit destructor can be virtual"
                    )
        if kind == "field":
            need(
                node,
                {
                    "type_id",
                    "semantic_parent_id",
                    "anonymous_member",
                    "bitfield",
                    "bit_width",
                    "offset_bits",
                },
            )
            if node["anonymous_member"] != (
                node["name"] == "" and not node["bitfield"]
            ):
                raise ValueError(
                    f"{node['id']} has inconsistent anonymous member naming"
                )
            if node["anonymous_member"]:
                target = types[node["type_id"]]
                if (
                    target["kind"] != "record"
                    or not declarations[target["declaration_id"]]["anonymous"]
                ):
                    raise ValueError(
                        f"{node['id']} anonymous storage must have an unnamed record type"
                    )
                if target["declaration_id"] not in declarations[
                    node["semantic_parent_id"]
                ].get("nested_declaration_ids", []):
                    raise ValueError(
                        f"{node['id']} anonymous storage type belongs to another context"
                    )
                if node["identity_kind"] != "source":
                    raise ValueError(
                        f"{node['id']} anonymous storage requires source identity"
                    )
            if node["bitfield"]:
                if (
                    node["bit_width"] is None
                    or not 0 <= int(node["bit_width"]) <= 4294967295
                ):
                    raise ValueError(
                        f"{node['id']} bitfield requires a concrete 32-bit width"
                    )
                if node["name"] == "" and node["identity_kind"] != "source":
                    raise ValueError(
                        f"{node['id']} unnamed bitfield requires source identity"
                    )
                if node["bit_width"] == 0 and node["name"]:
                    raise ValueError(
                        f"{node['id']} zero-width bitfield must be unnamed"
                    )
                target = types[types[node["type_id"]]["canonical_id"]]
                if target["kind"] != "enum":
                    integer_type(node["type_id"])
                address = [
                    c for c in node["capabilities"] if c["name"] == "field-address"
                ]
                if (
                    len(address) != 1
                    or address[0]["status"] != "unsupported"
                    or address[0]["reason_code"] != "BITFIELD_NOT_ADDRESSABLE"
                ):
                    raise ValueError(
                        f"{node['id']} bitfield must be explicitly non-addressable"
                    )
                parent = declarations[node["semantic_parent_id"]]
                if (
                    node["offset_bits"] is None
                    or parent.get("size_bits") is None
                    or int(node["offset_bits"]) + int(node["bit_width"])
                    > int(parent["size_bits"])
                ):
                    raise ValueError(
                        f"{node['id']} bitfield exceeds its owning record layout"
                    )
            elif node["bit_width"] is not None:
                raise ValueError(f"{node['id']} non-bitfield must have null width")
            parent = declarations[node["semantic_parent_id"]]
            if parent["kind"] != "record" or node["id"] not in parent.get(
                "field_ids", []
            ):
                raise ValueError(f"{node['id']} has inconsistent field ownership")

    # Inheritance is acyclic even though record field/type dependencies may cycle.
    # Validate the exact transitive virtual-base set in postorder, without
    # enumerating exponentially many paths through repeated diamond inheritance.
    records = {
        key: node for key, node in declarations.items() if node["kind"] == "record"
    }
    virtual_sets = {}
    ancestors = {}
    for root_id in records:
        active = set()
        stack = [(root_id, False)]
        while stack:
            identifier, leaving = stack.pop()
            if leaving:
                active.remove(identifier)
                node = records[identifier]
                expected = set()
                inherited = set()
                for base in node["bases"]:
                    target = base["declaration_id"]
                    expected.update(virtual_sets[target])
                    inherited.update(ancestors[target])
                    inherited.add(target)
                    if base["virtual"]:
                        expected.add(target)
                actual = {
                    base["declaration_id"] for base in node["virtual_base_offsets"]
                }
                if actual != expected:
                    raise ValueError(
                        f"{identifier} has inconsistent virtual base closure"
                    )
                virtual_sets[identifier] = expected
                ancestors[identifier] = inherited
                continue
            if identifier in active:
                raise ValueError(f"inheritance cycle at {identifier}")
            if identifier in virtual_sets:
                continue
            active.add(identifier)
            stack.append((identifier, True))
            stack.extend(
                (base["declaration_id"], False) for base in records[identifier]["bases"]
            )

    for node in declarations.values():
        if node["kind"] != "callable":
            continue
        parents = ancestors.get(node.get("semantic_parent_id"), set())
        # Reconstruct the nearest overridden declaration on each base path.
        # Checking only listed edges cannot detect a producer dropping an edge.
        expected_overrides = set()
        expected_implicit = set()
        if (
            node["callable_kind"] in {"method", "destructor", "conversion"}
            and not node["static"]
        ):
            pending = [
                base["declaration_id"]
                for base in records[node["semantic_parent_id"]]["bases"]
            ]
            visited = set()
            while pending:
                identifier = pending.pop()
                if identifier in visited:
                    continue
                visited.add(identifier)
                base = records[identifier]
                matches = []
                for member_id in base["callable_ids"]:
                    member = declarations[member_id]
                    if (
                        not member["virtual"]
                        or member["callable_kind"] != node["callable_kind"]
                    ):
                        continue
                    if node["callable_kind"] == "destructor" or (
                        all(
                            node[key] == member[key]
                            for key in (
                                "name",
                                "const",
                                "volatile",
                                "ref_qualifier",
                                "variadic",
                            )
                        )
                        and [parameter_key(p["type_id"]) for p in node["parameters"]]
                        == [parameter_key(p["type_id"]) for p in member["parameters"]]
                    ):
                        matches.append(member_id)
                if matches:
                    expected_overrides.update(matches)
                elif node["callable_kind"] == "destructor" and any(
                    slot["kind"] == "destructor"
                    and slot["state"] == "implicit"
                    and slot["virtual"]
                    for slot in base["special_members"]
                ):
                    expected_implicit.add(identifier)
                else:
                    pending.extend(edge["declaration_id"] for edge in base["bases"])
        if (
            set(node["overridden_declaration_ids"]) != expected_overrides
            or set(node["overridden_implicit_destructor_record_ids"])
            != expected_implicit
        ):
            raise ValueError(
                f"{node['id']} has incomplete or non-nearest override targets"
            )
        for identifier in node["overridden_declaration_ids"]:
            target = declarations[identifier]
            if (
                target.get("semantic_parent_id") not in parents
                or target["callable_kind"] != node["callable_kind"]
            ):
                raise ValueError(f"{node['id']} override must belong to a base record")
            if node["callable_kind"] != "destructor" and any(
                node[key] != target[key]
                for key in ("name", "const", "volatile", "ref_qualifier")
            ):
                raise ValueError(f"{node['id']} has an inconsistent override signature")
            if [parameter_key(p["type_id"]) for p in node["parameters"]] != [
                parameter_key(p["type_id"]) for p in target["parameters"]
            ]:
                raise ValueError(f"{node['id']} has inconsistent override parameters")
        if any(
            identifier not in parents
            for identifier in node["overridden_implicit_destructor_record_ids"]
        ):
            raise ValueError(
                f"{node['id']} implicit override must belong to a base record"
            )

    # Each context graph and namespace-alias chain must terminate. They are
    # independent of record/type dependency cycles, which are valid C++.
    for edge in ("semantic_parent_id", "lexical_parent_id", "target_namespace_id"):
        complete = set()
        for root_id in declarations:
            active = set()
            identifier = root_id
            while identifier is not None and identifier not in complete:
                if identifier in active:
                    raise ValueError(f"declaration context/alias cycle at {identifier}")
                active.add(identifier)
                identifier = declarations[identifier].get(edge)
            complete.update(active)

    # A record pointer can refer back to its record declaration, but pure type
    # structure (including alias targets) cannot contain a direct cycle. Use an
    # iterative traversal so validation does not consume Python recursion depth.
    complete = set()
    for root_id in types:
        active = set()
        stack = [(root_id, False)]
        while stack:
            identifier, leaving = stack.pop()
            if leaving:
                active.remove(identifier)
                complete.add(identifier)
                continue
            if identifier in active:
                raise ValueError(f"structural type cycle at {identifier}")
            if identifier in complete:
                continue
            active.add(identifier)
            stack.append((identifier, True))
            node = types[identifier]
            children = [
                node[key]
                for key in ("pointee_id", "element_id", "result_id")
                if key in node
            ]
            children.extend(node.get("parameter_ids", []))
            if node["kind"] == "alias":
                children.append(
                    declarations[node["declaration_id"]]["underlying_type_id"]
                )
            stack.extend((child, False) for child in children)


def validate_templates(types: dict, declarations: dict) -> None:
    pattern_fields = {"template_kind", "template_parameters", "pattern_spelling"}
    instance_fields = {
        "specialization_kind",
        "template_arguments",
        "instantiation_pattern_id",
        "instantiation_arguments",
        "point_of_instantiation",
    }
    common_fields = {
        "id",
        "kind",
        "name",
        "qualified_name",
        "usr",
        "identity_kind",
        "source",
        "access",
        "origin",
        "definition",
        "annotations",
        "capabilities",
        "semantic_parent_id",
        "lexical_parent_id",
        "canonical_declaration_id",
    }

    def parameters(values, parent_depth=None):
        depths = {p["depth"] for p in values}
        if len(depths) != 1 or (
            parent_depth is not None and depths != {parent_depth + 1}
        ):
            raise ValueError("template parameter depth is inconsistent")
        for index, parameter in enumerate(values):
            if parameter["index"] != index:
                raise ValueError("template parameter indices must follow source order")
            if parameter["kind"] == "template":
                parameters(parameter["parameters"], parameter["depth"])
            elif parameter["parameters"]:
                raise ValueError("only template parameters may have nested parameters")
            if parameter["kind"] == "non_type":
                if (
                    not parameter["type_spelling"]
                    or parameter["type_dependent"] is None
                ):
                    raise ValueError(
                        "non-type parameter requires declared type evidence"
                    )
            elif (
                parameter["type_spelling"] is not None
                or parameter["type_dependent"] is not None
            ):
                raise ValueError("only non-type parameters have declared type evidence")
            if (parameter["default_source"] is None) != (
                parameter["default_spelling"] is None
            ):
                raise ValueError("template parameter default evidence must be paired")
            if parameter["pack"] and parameter["default_source"] is not None:
                raise ValueError("template parameter pack cannot have a default")

    def argument(value):
        shapes = {
            "type": {"type_id"},
            "integral": {"type_id", "value", "signed", "bit_width"},
            "null_pointer": {"type_id"},
            "template": {"declaration_id"},
            "pack": {"elements"},
        }
        if value.keys() != shapes[value["kind"]] | {"kind"}:
            raise ValueError("template argument has missing or inapplicable fields")
        kind = value["kind"]
        if kind == "pack":
            for element in value["elements"]:
                if element["kind"] == "pack":
                    raise ValueError(
                        "concrete template packs cannot contain nested packs"
                    )
                argument(element)
            return
        if kind == "template":
            target = declarations[value["declaration_id"]]
            if (
                target["kind"] != "class_template"
                or target["template_kind"] != "primary"
            ):
                raise ValueError(
                    "template argument target must be a primary class template"
                )
            return
        target = types[value["type_id"]]
        if target["canonical_id"] != target["id"]:
            raise ValueError("semantic template arguments require canonical types")
        if kind == "integral":
            number, width = int(value["value"]), value["bit_width"]
            fits = (
                (number if number >= 0 else ~number).bit_length() < width
                if value["signed"]
                else number >= 0 and number.bit_length() <= width
            )
            if not fits:
                raise ValueError(
                    "template integral argument is outside its recorded range"
                )
            if target["kind"] == "enum":
                enumeration = declarations[target["declaration_id"]]
                if (
                    enumeration["underlying_signed"] != value["signed"]
                    or int(enumeration["size_bits"]) != width
                ):
                    raise ValueError(
                        "template integral argument disagrees with enum underlying type"
                    )
            elif target["kind"] == "builtin":
                name = target["spelling"]
                signed = name in {
                    "signed char",
                    "short",
                    "int",
                    "long",
                    "long long",
                    "__int128",
                }
                unsigned = name.startswith("unsigned ") or name in {
                    "bool",
                    "char16_t",
                    "char32_t",
                }
                if (
                    not (signed or unsigned or name in {"char", "wchar_t"})
                    or (signed and not value["signed"])
                    or (unsigned and value["signed"])
                ):
                    raise ValueError(
                        "template integral argument requires consistent integral type"
                    )
                if name == "bool" and (width != 1 or number not in (0, 1)):
                    raise ValueError(
                        "template boolean argument must be a one-bit value"
                    )
            else:
                raise ValueError("template integral argument requires an integral type")
        if (
            kind == "null_pointer"
            and target["kind"] != "pointer"
            and not (
                target["kind"] == "builtin" and target["spelling"] == "std::nullptr_t"
            )
        ):
            raise ValueError("null template argument requires pointer or nullptr type")

    def binding(arguments, signature):
        if len(arguments) != len(signature):
            raise ValueError(
                "template argument count must match parameter slots including packs"
            )
        for value, parameter in zip(arguments, signature):
            argument(value)
            if (value["kind"] == "pack") != parameter["pack"]:
                raise ValueError(
                    "template argument pack boundary disagrees with parameter"
                )
            for item in value["elements"] if parameter["pack"] else [value]:
                expected = {
                    "type": {"type"},
                    "non_type": {"integral", "null_pointer"},
                    "template": {"template"},
                }[parameter["kind"]]
                if item["kind"] not in expected:
                    raise ValueError("template argument kind disagrees with parameter")

    for node in declarations.values():
        pattern = node["kind"] == "class_template"
        instance = "specialization_kind" in node
        if pattern:
            if (
                not pattern_fields | {"primary_template_id", "record_tag"}
                <= node.keys()
            ):
                raise ValueError("class template is missing pattern metadata")
            if node.keys() - (
                common_fields | pattern_fields | {"primary_template_id", "record_tag"}
            ):
                raise ValueError(
                    "dependent template pattern must not claim instantiated facts"
                )
            parameters(node["template_parameters"])
            if node["template_kind"] == "primary":
                if (
                    node["primary_template_id"] is not None
                    or node["pattern_spelling"] is not None
                ):
                    raise ValueError(
                        "primary template cannot claim a partial-specialization target"
                    )
            elif not node["primary_template_id"] or not node["pattern_spelling"]:
                raise ValueError(
                    "partial specialization requires its primary and pattern spelling"
                )
            expected = {
                "name": "template-pattern",
                "status": "unknown",
                "reason_code": "DEPENDENT_TEMPLATE_PATTERN",
            }
            if node["capabilities"] != [expected]:
                raise ValueError(
                    "class template must explicitly classify its dependent pattern"
                )
        elif pattern_fields & node.keys():
            raise ValueError(
                "template pattern metadata belongs only to class templates"
            )
        if instance:
            if (
                node["kind"] != "record"
                or not instance_fields | {"primary_template_id"} <= node.keys()
            ):
                raise ValueError(
                    "class specialization requires record facts and complete metadata"
                )
            if node["identity_kind"] != "source":
                raise ValueError(
                    "class specialization requires argument-discriminated source identity"
                )
            primary = declarations[node["primary_template_id"]]
            if (
                primary["kind"] != "class_template"
                or primary["template_kind"] != "primary"
            ):
                raise ValueError(
                    "class specialization requires a primary class template"
                )
            binding(node["template_arguments"], primary["template_parameters"])
            instantiated = node["specialization_kind"] in {
                "implicit_instantiation",
                "explicit_instantiation_declaration",
                "explicit_instantiation_definition",
            }
            if instantiated != (
                node["instantiation_pattern_id"] is not None
                and node["instantiation_arguments"] is not None
            ):
                raise ValueError(
                    "instantiated class requires its selected pattern and deduced arguments"
                )
            if not instantiated and (
                node["instantiation_pattern_id"] is not None
                or node["instantiation_arguments"] is not None
            ):
                raise ValueError(
                    "uninstantiated or explicit specialization cannot claim a selected pattern"
                )
            if node["specialization_kind"] == "undeclared" and node["complete"]:
                raise ValueError(
                    "uninstantiated specialization cannot claim a complete layout"
                )
            if instantiated:
                selected = declarations[node["instantiation_pattern_id"]]
                if selected["kind"] != "class_template" or (
                    selected["id"] != primary["id"]
                    and selected["primary_template_id"] != primary["id"]
                ):
                    raise ValueError(
                        "instantiation pattern must belong to the same primary template"
                    )
                binding(
                    node["instantiation_arguments"], selected["template_parameters"]
                )
                if (
                    selected["id"] == primary["id"]
                    and node["template_arguments"] != node["instantiation_arguments"]
                ):
                    raise ValueError(
                        "primary instantiation arguments must match specialization arguments"
                    )
        elif instance_fields & node.keys():
            raise ValueError("specialization metadata requires a specialization kind")
        if node.get("primary_template_id") is not None:
            primary = declarations[node["primary_template_id"]]
            if (
                not (pattern or instance)
                or primary["kind"] != "class_template"
                or primary["template_kind"] != "primary"
                or primary["id"] == node["id"]
            ):
                raise ValueError("invalid primary template relationship")
            if primary["name"] != node["name"] or primary.get(
                "semantic_parent_id"
            ) != node.get("semantic_parent_id"):
                raise ValueError(
                    "template primary and specialization must share name and semantic context"
                )
        elif not pattern and "primary_template_id" in node:
            raise ValueError(
                "ordinary declaration cannot carry primary template metadata"
            )


def validate(schema: dict, document: dict) -> None:
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(document)
    validate_graph(document)
    if document["provenance"]["graph_digest"] != graph_digest(document):
        raise ValueError("graph_digest does not match normalized graph facts")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("--schema", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(
            json.loads(args.schema.read_text()), json.loads(args.document.read_text())
        )
    except (OSError, ValueError, KeyError, SchemaError, ValidationError) as error:
        print(f"icg-schema: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
