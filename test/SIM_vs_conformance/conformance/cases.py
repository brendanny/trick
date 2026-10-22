"""Command scripts for the golden byte captures.

Each case runs on a new connection. The first command pauses the session,
so only replies that the case asks for are captured. The golden file for a
case is goldens/<name>.bin.

Rules for a case:
  * Its reply must be the same on every run: no addresses, no PIDs, no paths.
  * It must not change SIM state that another case reads. A case that uses
    var_set puts the old value back at its end.
  * It must not trigger a known memory defect. Put those in
    test_known_defects.py, which starts its own SIM.
"""

from __future__ import annotations

from dataclasses import dataclass

P = "conf.vars."


@dataclass(frozen=True)
class Case:
    name: str
    commands: tuple[str, ...]

    def script(self) -> str:
        return "".join(line + "\n" for line in ("trick.var_pause()",) + self.commands)


def add(*names: str, units: str | None = None) -> tuple[str, ...]:
    if units is None:
        return tuple(f'trick.var_add("{n}")' for n in names)
    return tuple(f'trick.var_add("{n}", "{units}")' for n in names)


def v(*names: str) -> tuple[str, ...]:
    return tuple(P + n for n in names)


SEND = ("trick.var_send()",)

SCALARS = v(
    "c",
    "sc",
    "uc",
    "s",
    "us",
    "i32",
    "u32",
    "l",
    "ul",
    "ll",
    "ull",
    "f",
    "d",
    "b_true",
    "b_false",
    "wc",
    "color",
    "scoped",
)
# The ASCII writer reads every enum as a 4-byte int, so an enum with a short
# base type reads past its 2-byte buffer (VariableReference.cpp
# writeValueAscii). Binary cases send the 2 bytes as they are and keep it;
# test_known_defects.py covers the ASCII case.
SCALARS_ASCII = tuple(n for n in SCALARS if not n.endswith(".scoped"))
FLOAT_EDGES = v("d_neg", "d_tiny", "d_huge", "d_third", "d_inf", "d_nan", "f_third")
INT_LIMITS = v("i32_min", "ull_max")
# carr_full has no NUL. The ASCII writer runs strlen past its 8-byte buffer
# (VariableReference.cpp write_escaped_string); test_known_defects.py has it.
STRINGS = v(
    "carr",
    "cptr",
    "cptr_null",
    "cptr_escape",
    "str",
    "str_empty",
    "warr",
    "wptr",
)
ARRAYS = v(
    "iarr",
    "iarr[2]",
    "darr",
    "darr[1][1]",
    "darr[2][0]",
    "ucarr",
    "ucarr[3]",
    "barr",
    "barr[1]",
)
POINTERS_ASCII = v(
    "dptr",
    "dptr[0]",
    "dptr[3]",
    "iptr_null",
    "inner_ptr",
    "inner_ptr[0].a",
    "inner_ptr[0].b[1]",
    "vptr",
    "fp",
)
# Raw pointer values change from run to run, so binary cases read only
# NULL pointers and the values that pointers point to.
POINTERS_BINARY = v(
    "dptr[0]",
    "dptr[3]",
    "iptr_null",
    "inner_ptr[0].a",
    "inner_ptr[0].b[1]",
    "vptr",
    "fp",
)
STRUCTURED = v(
    "inner",
    "inner.a",
    "inner.b",
    "inner.b[1]",
    "bits",
    "bits.u3",
    "bits.u5",
    "bits.s4",
    "bits.s12",
)
# A whole STL container (no index) prints the container object's raw bytes,
# which hold heap addresses, so only indexed elements are captured.
STL_ASCII = v("vec[0]", "vec[2]", "vec[3]", "vec_empty[0]", "deq[3]")
STL_BINARY = v("vec[0]", "vec[2]", "vec[3]", "deq[3]")
BAD_REFS = (
    "no_such_object.x",
    P + "no_such_member",
    P + "iarr[9]",
    P + "dptr[4]",
    "conf..vars",
    P + "iarr[",
)


def binary_cases(prefix: str, mode_cmds: tuple[str, ...]) -> list[Case]:
    return [
        Case(f"{prefix}_scalars", mode_cmds + add(*SCALARS) + SEND),
        Case(
            f"{prefix}_float_edges", mode_cmds + add(*FLOAT_EDGES, *INT_LIMITS) + SEND
        ),
        Case(
            f"{prefix}_strings",
            mode_cmds
            + add(*v("carr", "cptr", "cptr_escape", "str", "str_empty", "warr", "wptr"))
            + SEND,
        ),
        Case(
            f"{prefix}_arrays",
            mode_cmds
            + add(*v("iarr[2]", "darr[1][1]", "ucarr[3]", "barr[1]", "iarr", "ucarr"))
            + SEND,
        ),
        Case(f"{prefix}_pointers", mode_cmds + add(*POINTERS_BINARY) + SEND),
        Case(
            f"{prefix}_structured",
            mode_cmds
            + add(
                *v("inner.a", "inner.b[1]", "bits.u3", "bits.u5", "bits.s4", "bits.s12")
            )
            + SEND,
        ),
        Case(f"{prefix}_stl", mode_cmds + add(*STL_BINARY) + SEND),
        Case(f"{prefix}_bad_refs", mode_cmds + add(*BAD_REFS) + SEND),
        Case(f"{prefix}_time", mode_cmds + add("time") + SEND),
    ]


# The old byteswap code swaps as many elements as the declared array has,
# even for one indexed element (VariableReference.cpp byteswap_var). That
# writes past the end of the buffer, so byteswap cases use only whole arrays,
# scalars and pointer elements. test_known_defects.py covers the rest.
def byteswap_cases(prefix: str, mode_cmds: tuple[str, ...]) -> list[Case]:
    return [
        Case(f"{prefix}_scalars", mode_cmds + add(*SCALARS) + SEND),
        Case(
            f"{prefix}_float_edges", mode_cmds + add(*FLOAT_EDGES, *INT_LIMITS) + SEND
        ),
        Case(
            f"{prefix}_strings",
            mode_cmds
            + add(*v("carr", "cptr", "cptr_escape", "str", "str_empty", "warr", "wptr"))
            + SEND,
        ),
        Case(
            f"{prefix}_whole_arrays",
            mode_cmds + add(*v("iarr", "ucarr", "darr", "barr")) + SEND,
        ),
        Case(
            f"{prefix}_pointers",
            mode_cmds
            + add(*v("dptr[0]", "dptr[3]", "iptr_null", "inner_ptr[0].a", "vptr", "fp"))
            + SEND,
        ),
        Case(
            f"{prefix}_structured",
            mode_cmds
            + add(*v("inner.a", "bits.u3", "bits.u5", "bits.s4", "bits.s12"))
            + SEND,
        ),
        Case(f"{prefix}_bad_refs", mode_cmds + add(*BAD_REFS) + SEND),
        Case(f"{prefix}_time", mode_cmds + add("time") + SEND),
    ]


CASES: list[Case] = [
    # ASCII values
    Case("ascii_scalars", add(*SCALARS_ASCII) + SEND),
    Case("ascii_float_edges", add(*FLOAT_EDGES) + SEND),
    Case("ascii_int_limits", add(*INT_LIMITS) + SEND),
    Case("ascii_strings", add(*STRINGS) + SEND),
    Case("ascii_arrays", add(*ARRAYS) + SEND),
    Case("ascii_big_array_split", add(P + "big") + SEND),
    Case("ascii_pointers", add(*POINTERS_ASCII) + SEND),
    Case("ascii_structured", add(*STRUCTURED) + SEND),
    Case("ascii_stl", add(*STL_ASCII) + SEND),
    Case("ascii_bad_refs", add(*BAD_REFS) + SEND),
    Case("ascii_time", add("time") + SEND),
    Case(
        "ascii_mixed_good_and_bad", add(P + "i32", "no_such_object.x", P + "d") + SEND
    ),
    # Units
    Case(
        "ascii_units_on_add",
        (
            f'trick.var_add("{P}pos", "ft")',
            f'trick.var_add("{P}ang", "deg")',
            f'trick.var_add("{P}speed", "ft/s")',
            f'trick.var_add("{P}temp", "degF")',
            f'trick.var_add("{P}count_m", "cm")',
            f'trick.var_add("{P}darr", "cm")',
            f'trick.var_add("{P}dptr[1]", "mm")',
            f'trick.var_add("{P}ratio", "1")',
        )
        + SEND,
    ),
    Case(
        "ascii_units_special",
        (
            f'trick.var_add("{P}pos", "xx")',
            f'trick.var_add("{P}unitless", "xx")',
            f'trick.var_add("{P}pos", "--")',
            f'trick.var_add("time", "xx")',
        )
        + SEND,
    ),
    Case(
        "ascii_units_invalid",
        (
            f'trick.var_add("{P}pos", "s")',
            f'trick.var_add("{P}pos", "not_a_unit")',
            f'trick.var_add("{P}unitless", "m")',
        )
        + SEND,
    ),
    Case(
        "ascii_var_units",
        add(*v("pos", "ang"))
        + (
            f'trick.var_units("{P}pos", "km")',
            f'trick.var_units("{P}ang", "deg")',
        )
        + SEND,
    ),
    # List changes
    Case(
        "ascii_duplicate_add",
        add(*v("i32", "pos", "i32")) + (f'trick.var_units("{P}i32", "--")',) + SEND,
    ),
    Case(
        "ascii_remove_first_match",
        add(*v("i32", "d", "i32", "f")) + (f'trick.var_remove("{P}i32")',) + SEND,
    ),
    Case(
        "ascii_remove_missing", add(P + "i32") + (f'trick.var_remove("{P}d")',) + SEND
    ),
    Case("ascii_clear_then_send", add(*v("i32", "d")) + ("trick.var_clear()",) + SEND),
    Case("ascii_send_empty_list", SEND),
    Case("ascii_send_twice", add(P + "i32") + SEND + SEND),
    # One-off replies
    Case("ascii_send_once_single", (f'trick.var_send_once("{P}i32")',)),
    Case("ascii_send_once_multi", (f'trick.var_send_once("{P}i32,{P}d,{P}str", 3)',)),
    Case("ascii_send_once_count_mismatch", (f'trick.var_send_once("{P}i32,{P}d", 3)',)),
    Case("ascii_send_once_bad_ref", (f'trick.var_send_once("{P}no_such_member")',)),
    Case(
        "ascii_send_once_space_after_comma",
        (f'trick.var_send_once("{P}i32, {P}d", 2)',),
    ),
    Case(
        "ascii_send_once_keeps_list",
        add(P + "d") + (f'trick.var_send_once("{P}i32")',) + SEND,
    ),
    Case(
        "ascii_exists",
        (
            f'trick.var_exists("{P}i32")',
            f'trick.var_exists("{P}no_such_member")',
            f'trick.var_exists("{P}iarr[4]")',
            f'trick.var_exists("{P}iarr[5]")',
        ),
    ),
    Case(
        "ascii_list_size", add(*v("i32", "d", "str")) + ("trick.var_send_list_size()",)
    ),
    Case(
        "ascii_stl_size",
        (
            f'trick.var_get_stl_size("{P}vec")',
            f'trick.var_get_stl_size("{P}deq")',
            f'trick.var_get_stl_size("{P}vec_empty")',
            f'trick.var_get_stl_size("{P}i32")',
            f'trick.var_get_stl_size("{P}no_such_member")',
        ),
    ),
    # var_set: each value is put back at the end
    Case(
        "ascii_var_set",
        (
            f'trick.var_set("{P}settable", 99)',
            f'trick.var_set("{P}settable_d", 250.0, "cm")',
            f'trick.var_set("{P}settable_str", "after")',
            f'trick.var_set("{P}read_only", 1)',
            f'trick.var_set("{P}no_such_member", 1)',
            f'trick.var_send_once("{P}settable,{P}settable_d,{P}settable_str,{P}read_only", 4)',
            f'trick.var_set("{P}settable", 12)',
            f'trick.var_set("{P}settable_d", 2.0)',
            f'trick.var_set("{P}settable_str", "before")',
            f'trick.var_send_once("{P}settable,{P}settable_d,{P}settable_str", 3)',
        ),
    ),
    # Files and stdio
    Case("ascii_send_file", ('trick.send_file("data/send_file.txt")',)),
    Case("ascii_send_file_missing", ('trick.send_file("data/no_such_file.txt")',)),
    Case(
        "ascii_stdio",
        (
            "trick.var_set_send_stdio(1)",
            'print("hello from stdio")',
            'trick.var_write_stdio(2, "error text\\n")',
            "trick.var_set_send_stdio(0)",
            'print("not sent")',
        ),
    ),
    # Python lines that are not var_* commands
    Case(
        "python_statement", ("x_conf = 6 * 7", 'trick.var_send_once("conf.vars.i32")')
    ),
    Case("python_syntax_error", ("this is not python",)),
    Case(
        "python_exception_stops_batch",
        (
            'trick.var_send_once("conf.vars.i32")',
            "raise RuntimeError('stop')",
            'trick.var_send_once("conf.vars.d")',
        ),
    ),
    # Binary: names, no names, byte swap
    *binary_cases("binary", ("trick.var_binary()",)),
    *binary_cases("nonames", ("trick.var_binary_nonames()",)),
    *byteswap_cases("byteswap", ("trick.var_binary()", "trick.var_byteswap(True)")),
    *byteswap_cases(
        "byteswap_nonames", ("trick.var_binary_nonames()", "trick.var_byteswap(True)")
    ),
    Case(
        "binary_units_ignored",
        ("trick.var_binary()",)
        + (
            f'trick.var_add("{P}pos", "ft")',
            f'trick.var_add("{P}darr", "cm")',
        )
        + SEND,
    ),
    Case(
        "binary_big_array_skipped",
        ("trick.var_binary()",) + add(P + "i32", P + "big", P + "d") + SEND,
    ),
    Case(
        "binary_whole_arrays",
        ("trick.var_binary()",) + add(*v("darr", "barr", "carr_full", "warr")) + SEND,
    ),
    Case(
        "binary_send_once",
        ("trick.var_binary()", f'trick.var_send_once("{P}i32,{P}d", 2)'),
    ),
    Case(
        "binary_exists",
        (
            "trick.var_binary()",
            f'trick.var_exists("{P}i32")',
            f'trick.var_exists("{P}nope")',
        ),
    ),
    Case(
        "binary_list_size",
        ("trick.var_binary()",) + add(*v("i32", "d")) + ("trick.var_send_list_size()",),
    ),
    Case(
        "binary_stl_size",
        (
            "trick.var_binary()",
            f'trick.var_get_stl_size("{P}vec")',
            f'trick.var_get_stl_size("{P}nope")',
        ),
    ),
    Case(
        "binary_send_file",
        ("trick.var_binary()", 'trick.send_file("data/send_file.txt")'),
    ),
    Case(
        "byteswap_fixed_replies",
        (
            "trick.var_binary()",
            "trick.var_byteswap(True)",
            f'trick.var_exists("{P}i32")',
            f'trick.var_get_stl_size("{P}vec")',
        )
        + add(P + "i32")
        + ("trick.var_send_list_size()",),
    ),
    Case(
        "nonames_then_ascii",
        ("trick.var_binary_nonames()",)
        + add(P + "i32")
        + SEND
        + ("trick.var_ascii()",)
        + SEND,
    ),
]

NAMES = [c.name for c in CASES]
assert len(NAMES) == len(set(NAMES)), "case names must be unique"
