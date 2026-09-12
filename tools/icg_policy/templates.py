"""First-use metadata for bounded, reachable scalar/array/structured template tables.

Types and arguments are followed by graph IDs; only the legacy ABI spelling is
rendered here. Dependent patterns never become runtime tables of their own.
"""

from __future__ import annotations

import re

from tools.icg_policy import enums, rules, storage


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

    def shape(type_id: str) -> tuple[dict, list[int]]:
        node = types[types[type_id]["canonical_id"]]
        dimensions = []
        while node["kind"] == "array":
            if node["extent"] is None or not 1 <= int(node["extent"]) <= 2147483647:
                fail("template storage requires positive fixed array extents")
            dimensions.append(int(node["extent"]))
            if len(dimensions) > 8:
                fail("template storage exceeds TRICK_MAX_INDEX")
            node = types[types[node["element_id"]]["canonical_id"]]
        if any(node["qualifiers"].values()):
            fail("template storage requires unqualified types")
        return node, dimensions

    def enum_type(node: dict) -> str:
        declaration = nodes[node["declaration_id"]]
        selected(declaration)
        return enums.template_type(declaration, nodes, types)

    def enum_ids(type_id: str) -> set[str]:
        node, _ = shape(type_id)
        if node["kind"] == "enum":
            enum_type(node)
            return {node["declaration_id"]}
        if node["kind"] == "record":
            return set().union(
                *(
                    enum_ids(a["type_id"])
                    for a in nodes[node["declaration_id"]]["template_arguments"]
                )
            )
        return set()

    def cpp_type(type_id: str) -> str:
        node, dimensions = shape(type_id)
        if node["kind"] == "record":
            name = record_cpp(nodes[node["declaration_id"]])
        elif node["kind"] == "enum":
            # Legacy's canonical template spelling retains the elaborated keyword.
            name = "enum " + enum_type(node)
        else:
            name = storage.resolve(
                dict(
                    type_id=node["id"],
                    name="argument",
                    qualified_name="template argument",
                    bitfield=False,
                ),
                types,
            )["cpp_type"]
        return name + "".join(f"[{extent}]" for extent in dimensions)

    spellings = {}

    def record_cpp(record: dict) -> str:
        if record["id"] not in spellings:
            primary = primary_for(record)
            if any(a["kind"] != "type" for a in record["template_arguments"]):
                fail("template argument is outside the type profile")
            arguments = ", ".join(
                cpp_type(a["type_id"]) for a in record["template_arguments"]
            )
            spellings[record["id"]] = (
                identifier(primary)
                + "<"
                + arguments
                + (" >" if arguments.endswith(">") else ">")
            )
        return spellings[record["id"]]

    symbols = {}

    def symbol_for(record: dict) -> str:
        if record["id"] not in first_uses:
            fail("structured dependency has no active first-use evidence")
        use = nodes[first_uses[record["id"]][-1]]
        owner = nodes[use["semantic_parent_id"]]
        symbol = (
            identifier(owner)
            + "_"
            + identifier(use)
            + "_"
            + re.sub(r"[^A-Za-z0-9_]", "_", record_cpp(record))
        )
        if symbol in symbols and symbols[symbol] != record["id"]:
            fail("legacy template symbol collision")
        symbols[symbol] = record["id"]
        return symbol

    instances, pending, unit_values = {}, set(), {}

    def include(record_id: str) -> None:
        if record_id in instances:
            return
        if record_id in pending:
            fail("recursive by-value template storage is not supported")
        pending.add(record_id)
        record = nodes[record_id]
        primary = primary_for(record)
        if not 0 < int(record["size_bits"]) <= 2147483647 * 8:
            fail("template element size must fit positive ATTRIBUTES.size")
        path = first_uses[record_id]
        name = record_cpp(record)
        symbol = symbol_for(record)
        dependencies = set()
        enum_dependencies = set().union(
            *(enum_ids(a["type_id"]) for a in record["template_arguments"])
        )
        fields = []
        for member_id in record["field_ids"]:
            member = nodes[member_id]
            index, value = annotation(member)
            included = value["io"] != 0
            if included and member["access"] != "public":
                fail("template member access requires a public field")
            if included and (member["bitfield"] or member["static"]):
                fail("template bitfield/static emission is not characterized")
            key = name + "_" + identifier(member)
            member_storage = None
            if included:
                element, dimensions = shape(member["type_id"])
                if element["kind"] == "record":
                    child = nodes[element["declaration_id"]]
                    member_storage = dict(
                        element_type_id=element["id"],
                        record_id=child["id"],
                        type_name=symbol_for(child),
                        cpp_type=cpp_type(member["type_id"]),
                        trick_type="TRICK_STRUCTURED",
                        dimensions=dimensions,
                    )
                    dependencies.add(child["id"])
                    include(child["id"])
                elif element["kind"] == "enum":
                    enum_name = enum_type(element)
                    member_storage = dict(
                        element_type_id=element["id"],
                        enum_id=element["declaration_id"],
                        type_name=enum_name,
                        cpp_type=enum_name + "".join(f"[{n}]" for n in dimensions),
                        trick_type="TRICK_ENUMERATED",
                        dimensions=dimensions,
                    )
                    enum_dependencies.add(element["declaration_id"])
                else:
                    member_storage = storage.resolve(member, types)
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
                        storage=member_storage,
                        units_map_key=key,
                    ),
                )
            )
        instances[record_id] = dict(
            field_id=path[-1],
            requested_field_ids=sorted(requested.get(record_id, [])),
            dependency_path=path,
            dependency_record_ids=sorted(dependencies),
            dependency_enum_ids=sorted(enum_dependencies),
            record_id=record_id,
            primary_template_id=primary["id"],
            argument_type_ids=[a["type_id"] for a in record["template_arguments"]],
            cpp_type=name,
            symbol=symbol,
            init_function="init_attr" + symbol,
            fields=fields,
        )
        pending.remove(record_id)

    for record_id in requested:
        include(record_id)
    return sorted(instances.values(), key=lambda instance: instance["symbol"])
