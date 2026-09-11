"""First-use metadata for bounded, reachable scalar/array template tables.

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

    # An unselected header can contain an earlier consumer absent from the
    # supported-declaration closure. Require coverage before inferring first use.
    if any(
        f["classification"] == "user" and f["id"] not in request["file_ids"]
        for f in files.values()
    ):
        fail("template traversal requires every captured user file to be selected")

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

    def target(field: dict) -> dict | None:
        node = types[types[field["type_id"]]["canonical_id"]]
        while node["kind"] in (
            "array",
            "pointer",
            "lvalue_reference",
            "rvalue_reference",
        ):
            child = node.get("element_id") or node.get("pointee_id")
            node = types[types[child]["canonical_id"]]
        record = nodes.get(node.get("declaration_id"))
        return record if record and record.get("primary_template_id") else None

    # Serialized graph IDs are not source order. Limit competing ordinary roots
    # to one physical file until include/namespace traversal is characterized.
    owners = []
    for node in nodes.values():
        if node["kind"] != "record" or node.get("primary_template_id"):
            continue
        uses = [nodes[i] for i in node["field_ids"] if target(nodes[i])]
        if not uses:
            continue
        selected(node)
        if not any(annotation(use)[1]["io"] for use in uses):
            continue
        if node["id"] not in roots or node.get("semantic_parent_id") or node["bases"]:
            fail(
                "template traversal requires selected global ordinary roots without bases"
            )
        owners.append(node)
    if len({n["source"]["spelling"]["file_id"] for n in owners}) > 1:
        fail(
            "template first-use order across ordinary roots in different files is not characterized"
        )

    def primary_for(record: dict) -> dict:
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
        return primary

    first_uses, reached = {}, {}

    def visit(owner: dict, path: list[str]) -> None:
        for use in sorted(
            (nodes[i] for i in owner["field_ids"]),
            key=lambda n: n["source"]["spelling"]["offset"],
        ):
            member_id = use["id"]
            record = target(use)
            if record is None or annotation(use)[1]["io"] == 0:
                continue
            if use["access"] != "public" or use["static"] or use["bitfield"]:
                fail("template traversal requires public nonstatic fields")
            selected(record)
            if (
                record["bases"]
                or any(
                    nodes[i]["kind"] != "alias"
                    for i in record["nested_declaration_ids"]
                )
                or not record["complete"]
            ):
                fail(
                    "template traversal requires complete definitions without bases or nested declarations"
                )
            primary_for(record)
            reached[member_id] = record["id"]
            if record["id"] in first_uses:
                continue
            dependency_path = path + [member_id]
            # Legacy inserts into its cache before recursively visiting members.
            first_uses[record["id"]] = dependency_path
            visit(record, dependency_path)

    for owner in sorted(owners, key=lambda n: n["source"]["spelling"]["offset"]):
        visit(owner, [])

    requested = {}
    for field_id in request["template_field_ids"]:
        use = nodes.get(field_id)
        if use is None or use["kind"] != "field" or field_id not in reached:
            fail(
                "template request must identify an active field reachable from the selected roots"
            )
        type_node = types[types[use["type_id"]]["canonical_id"]]
        while type_node["kind"] == "array":
            if (
                type_node["extent"] is None
                or not 1 <= int(type_node["extent"]) <= 2147483647
            ):
                fail("template array use requires a positive fixed extent")
            type_node = types[types[type_node["element_id"]]["canonical_id"]]
        if type_node["kind"] != "record" or any(type_node["qualifiers"].values()):
            fail(
                "template request requires an unqualified object or fixed array of objects"
            )
        requested.setdefault(reached[field_id], []).append(field_id)

    instances, symbols, unit_values = [], set(), {}
    for record_id, requested_fields in requested.items():
        path = first_uses[record_id]
        field_id = path[-1]
        use = nodes[field_id]
        owner = nodes[use["semantic_parent_id"]]
        record = nodes[record_id]
        primary = primary_for(record)
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
            if included and (member["bitfield"] or member["static"]):
                fail("template bitfield/static emission is not characterized")
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
                requested_field_ids=sorted(requested_fields),
                dependency_path=path,
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
