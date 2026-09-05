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
    )
    type_links = ("type_id", "underlying_type_id", "return_type_id")
    for node in declarations.values():
        context = node["id"]
        source(node["source"], context)
        for field in declaration_links:
            if field in node:
                require(node[field], declarations, f"{context}.{field}")
        for identifier in node.get("field_ids", []) + node.get(
            "nested_declaration_ids", []
        ):
            require(identifier, declarations, context)
        for field in type_links:
            if field in node:
                require(node[field], types, f"{context}.{field}")
        for base in node.get("bases", []):
            require(base["declaration_id"], declarations, f"{context}.bases")
            require(base["type_id"], types, f"{context}.bases")
            source(base["source"], f"{context}.bases")
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
