"""Operation-specific legacy lifecycle decisions for non-template scalar records."""

from __future__ import annotations

from tools.icg_policy import storage
from tools.icg_policy.rules import PolicyError


def member(record: dict, declarations: dict, kind: str) -> dict:
    index, slot = next(
        (i, item)
        for i, item in enumerate(record["special_members"])
        if item["kind"] == kind
    )
    ids = slot["declaration_ids"]
    if slot["state"] == "suppressed":
        available, rule, virtual = False, "NO_DECLARED_SPECIAL_MEMBER", False
    else:
        if slot["state"] == "implicit":
            deleted, access, virtual = slot["deleted"], "public", slot["virtual"]
        elif slot["state"] == "user_declared" and len(ids) == 1:
            declaration = declarations[ids[0]]
            deleted, access, virtual = (
                declaration["deleted"],
                declaration["access"],
                declaration["virtual"],
            )
        else:
            raise PolicyError(
                "ICG_POLICY_LIFECYCLE_MEMBER", "ambiguous special-member evidence"
            )
        rule = (
            "DELETED_SPECIAL_MEMBER"
            if deleted
            else "NON_PUBLIC_SPECIAL_MEMBER"
            if access != "public"
            else "PUBLIC_SPECIAL_MEMBER"
        )
        available = rule == "PUBLIC_SPECIAL_MEMBER"
    return dict(
        special_member_index=index,
        declaration_ids=list(ids),
        available=available,
        rule=rule,
        virtual=virtual,
    )


def resolve(record: dict, declarations: dict, types: dict, symbol: str) -> dict:
    if record["record_tag"] == "union" or int(record["alignment_bits"]) > 128:
        raise PolicyError(
            "ICG_POLICY_LIFECYCLE_STORAGE",
            "unions and over-aligned allocation are outside this profile",
        )
    # Construction concerns every field, even fields omitted from metadata by I/O.
    for identifier in record["field_ids"]:
        storage.resolve(declarations[identifier], types)
    for identifier in record["callable_ids"]:
        if declarations[identifier]["name"] in (
            "operator new",
            "operator new[]",
            "operator delete",
            "operator delete[]",
        ):
            raise PolicyError(
                "ICG_POLICY_LIFECYCLE_ALLOCATION",
                "class-specific allocation/deallocation is outside this profile",
            )
    constructor = member(record, declarations, "default_constructor")
    destructor = member(record, declarations, "destructor")
    if (
        destructor["available"]
        and not destructor["virtual"]
        and any(declarations[i]["virtual"] for i in record["callable_ids"])
    ):
        raise PolicyError(
            "ICG_POLICY_LIFECYCLE_DELETE",
            "polymorphic scalar deletion requires a virtual destructor",
        )
    placement = constructor["available"] and not record["abstract"]
    allocation = (
        "raw_storage" if record["pod"] else "construct" if placement else "absent"
    )
    destruction = (
        "absent" if not destructor["available"] else "noop" if record["pod"] else "loop"
    )
    deletion = (
        "absent"
        if not destructor["available"]
        else "noop"
        if record["pod"]
        else "scalar"
    )

    def operation(name, action, rule):
        return dict(symbol=f"io_src_{name}_{symbol}", action=action, rule=rule)

    return dict(
        domain="positive-count-nonthrowing",
        default_constructor=constructor,
        destructor=destructor,
        default_placement=placement,
        allocate=operation(
            "allocate",
            allocation,
            "LEGACY_POD_RAW_STORAGE"
            if record["pod"]
            else "ABSTRACT_RECORD"
            if record["abstract"]
            else constructor["rule"],
        ),
        destruct=operation(
            "destruct",
            destruction,
            destructor["rule"]
            if destruction == "absent"
            else "LEGACY_POD_NOOP"
            if record["pod"]
            else "FORWARD_DESTRUCTION_NO_FREE",
        ),
        delete=operation(
            "delete",
            deletion,
            destructor["rule"]
            if deletion == "absent"
            else "LEGACY_POD_NOOP"
            if record["pod"]
            else "SCALAR_NEW_OWNERSHIP",
        ),
    )
