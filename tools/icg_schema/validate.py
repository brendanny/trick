#!/usr/bin/env python3
"""Validate an extracted-facts document against its schema and graph invariants."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, SchemaError, ValidationError


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
        for field in declaration_links:
            if field in node:
                require(node[field], declarations, f"{context}.{field}")
        for identifier in (
            node.get("field_ids", [])
            + node.get("nested_declaration_ids", [])
            + node.get("declaration_ids", [])
        ):
            require(identifier, declarations, context)
        for reopening in node.get("reopening_sources", []):
            source(reopening, f"{context}.reopening_sources")
        for field in type_links:
            if field in node:
                require(node[field], types, f"{context}.{field}")
        for base in node.get("bases", []):
            require(base["declaration_id"], declarations, f"{context}.bases")
            require(base["type_id"], types, f"{context}.bases")
            source(base["source"], f"{context}.bases")
        for base in node.get("virtual_base_offsets", []):
            require(
                base["declaration_id"], declarations, f"{context}.virtual_base_offsets"
            )
        for parameter in node.get("parameters", []):
            require(parameter["type_id"], types, f"{context}.parameters")
        for annotation in node["annotations"]:
            source(annotation["source"], f"{context}.annotations")

    for file in files.values():
        for include in file["includes"]:
            require(include["file_id"], files, f"{file['id']}.includes")
            source(include["source"], f"{file['id']}.includes")
    for index, diagnostic in enumerate(document["diagnostics"]):
        if diagnostic["source"] is not None:
            source(diagnostic["source"], f"diagnostics[{index}]")

    for node in declarations.values():
        for enumerator in node.get("enumerators", []):
            source(enumerator["source"], f"{node['id']}.enumerators")
            for annotation in enumerator["annotations"]:
                source(annotation["source"], f"{node['id']}.enumerators.annotations")

    validate_structure(types, declarations)


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

    for node in declarations.values():
        kind = node["kind"]
        if node["identity_kind"] == "usr" and not node["usr"]:
            raise ValueError(f"{node['id']} has no USR for its identity")
        if kind in {"record", "field", "enum", "alias", "namespace", "namespace_alias"}:
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
                and kind in {"record", "enum", "alias"}
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
                ("nested_declaration_ids", {"record", "alias", "enum", "callable"}),
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
    for root_id in records:
        active = set()
        stack = [(root_id, False)]
        while stack:
            identifier, leaving = stack.pop()
            if leaving:
                active.remove(identifier)
                node = records[identifier]
                expected = set()
                for base in node["bases"]:
                    target = base["declaration_id"]
                    expected.update(virtual_sets[target])
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


def validate(schema: dict, document: dict) -> None:
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(document)
    validate_graph(document)


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
