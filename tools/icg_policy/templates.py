"""Per-use metadata for direct, global, scalar/array class-template members.

Types and arguments are followed by graph IDs; only the legacy ABI spelling is
rendered here. Dependent patterns never become runtime tables of their own.
"""

from __future__ import annotations

import re

from tools.icg_policy import rules, storage


def resolve(facts: dict, request: dict, effective: dict, policies: dict) -> list[dict]:
    nodes = {n["id"]: n for n in facts["declarations"]}
    types = {n["id"]: n for n in facts["types"]}
    files = {n["id"]: n for n in facts["files"]}
    roots = {
        r["declaration_id"]
        for r in facts["provenance"]["selection"]["roots"]
        if r["source"]["expansion"]["file_id"] in request["file_ids"]
    }

    def fail(message: str) -> None:
        raise rules.PolicyError("ICG_POLICY_TEMPLATE", message)

    def identifier(node: dict) -> str:
        if not re.fullmatch(r"[A-Za-z_]\w*", node["name"], re.ASCII):
            fail("template output requires an ASCII identifier")
        return node["name"]

    def selected(node: dict) -> dict:
        if node["source"]["macro_expansion"]:
            fail("template selection/comment evidence must be physical")
        policy = policies.get(node["source"]["spelling"]["file_id"])
        if policy is None or policy["excluded"]:
            fail("template use and definition must belong to requested, included files")
        ignored = set(policy["ignore_types"]) | set(effective["ignore_types"])
        if node["name"] in ignored or node["qualified_name"] in ignored:
            fail("explicit template request selects an ignored type")
        return policy

    def annotation(node: dict) -> tuple[int | None, dict]:
        policy = selected(node)
        file = files[node["source"]["spelling"]["file_id"]]
        index = (
            None
            if policy["no_comment"]
            else rules.line_comments(file).get(node["source"]["end"]["line"])
        )
        return index, rules.annotation(
            file["comments"][index]["payload"] if index is not None else None
        )

    instances, symbols, unit_values = [], set(), {}
    for field_id in request["template_field_ids"]:
        use = nodes.get(field_id)
        if use is None or use["kind"] != "field":
            fail("template request must identify field declarations")
        owner = nodes.get(use["semantic_parent_id"])
        if (
            owner is None
            or owner["id"] not in roots
            or owner["kind"] != "record"
            or owner.get("semantic_parent_id") is not None
            or owner.get("primary_template_id")
            or owner["bases"]
            or use["access"] != "public"
            or use["bitfield"]
        ):
            fail(
                "template use requires a public direct field of a selected global ordinary record"
            )
        selected(owner)
        if annotation(use)[1]["io"] == 0:
            fail("explicit template request selects an I/O-disabled field")
        type_node = types[use["type_id"]]
        if (
            type_node["kind"] != "record"
            or type_node["id"] != type_node["canonical_id"]
            or any(type_node["qualifiers"].values())
        ):
            fail(
                "template use requires a direct unqualified specialization, without aliases or arrays of instances"
            )
        record = nodes[type_node["declaration_id"]]
        # Legacy caches the first field-based name for a specialization. Source
        # traversal across repeated/nested uses is not modeled by this profile.
        # Refuse ambiguity instead of inventing a second table or a first-use order.
        for other in nodes.values():
            if other["kind"] != "field" or other["id"] == field_id:
                continue
            other_type = types[types[other["type_id"]]["canonical_id"]]
            while other_type["kind"] in (
                "array",
                "pointer",
                "lvalue_reference",
                "rvalue_reference",
            ):
                child = other_type.get("element_id") or other_type.get("pointee_id")
                other_type = types[types[child]["canonical_id"]]
            if other_type["id"] == type_node["id"] and annotation(other)[1]["io"]:
                fail(
                    "repeated template uses require a characterized legacy first-use naming policy"
                )
        primary = nodes.get(record.get("primary_template_id"))
        if (
            primary is None
            or primary["origin"] != "user"
            or primary.get("semantic_parent_id") is not None
            or record.get("specialization_kind") != "implicit_instantiation"
            or record.get("instantiation_pattern_id") != primary["id"]
            or not record["complete"]
            or record["bases"]
            or not record["standard_layout"]
            or record["record_tag"] == "union"
            or any(
                p["kind"] != "type" or p["pack"] or p["default_spelling"] is not None
                for p in primary["template_parameters"]
            )
        ):
            fail(
                "only complete primary instantiations with nonpack type parameters and no defaults are characterized"
            )
        selected(primary)
        selected(record)
        arguments = []
        for arg in record["template_arguments"]:
            if arg["kind"] != "type":
                fail("template argument is outside the scalar/array type profile")
            arguments.append(
                storage.resolve(
                    dict(
                        type_id=arg["type_id"],
                        name="argument",
                        qualified_name=record["qualified_name"],
                        bitfield=False,
                    ),
                    types,
                )["cpp_type"]
            )
        cpp_type = identifier(primary) + "<" + ", ".join(arguments) + ">"
        symbol = (
            identifier(owner)
            + "_"
            + identifier(use)
            + "_"
            + re.sub(r"[^A-Za-z0-9_]", "_", cpp_type)
        )
        if symbol in symbols:
            fail("legacy template symbol collision")
        symbols.add(symbol)
        fields = []
        for member_id in record["field_ids"]:
            member = nodes[member_id]
            index, value = annotation(member)
            included = value["io"] != 0
            if included and member["access"] != "public":
                fail("template member access requires a public field")
            if included and member["bitfield"]:
                fail("template bitfield emission is not characterized")
            key = cpp_type + "_" + identifier(member)
            if included:
                if key in unit_values and unit_values[key] != value["units"]:
                    fail("legacy template UnitsMap key collision")
                unit_values[key] = value["units"]
            fields.append(
                dict(
                    declaration_id=member_id,
                    source=member["source"],
                    parent_id=record["id"],
                    decision="include" if included else "omit",
                    rule="NUMERIC_OFFSET_METADATA" if included else "IO_DISABLED",
                    metadata=dict(
                        type_id=member["type_id"],
                        comment_index=index,
                        annotation=value,
                        access=dict(
                            operation="member-access-in-init-attributes",
                            allowed=member["access"] == "public",
                            rule="PUBLIC_MEMBER"
                            if member["access"] == "public"
                            else "NO_ACCESS_GRANT",
                            friend_indices=[],
                            legacy_prefix_indices=[],
                            compatibility=None,
                        ),
                        storage=storage.resolve(member, types) if included else None,
                        units_map_key=key,
                    ),
                )
            )
        instances.append(
            dict(
                field_id=field_id,
                record_id=record["id"],
                primary_template_id=primary["id"],
                argument_type_ids=[a["type_id"] for a in record["template_arguments"]],
                cpp_type=cpp_type,
                symbol=symbol,
                init_function="init_attr" + symbol,
                fields=fields,
            )
        )
    return sorted(instances, key=lambda instance: instance["symbol"])
