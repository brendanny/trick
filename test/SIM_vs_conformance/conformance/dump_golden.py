"""Print a golden file so a person can review it.

    python3 dump_golden.py goldens/binary_scalars.bin [--nonames] [--byteswap]

ASCII files print as text. Binary files print one line per variable.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

TYPE_NAMES = {
    1: "char",
    2: "uchar",
    3: "string",
    4: "short",
    5: "ushort",
    6: "int",
    7: "uint",
    8: "long",
    9: "ulong",
    10: "float",
    11: "double",
    12: "bitfield",
    13: "ubitfield",
    14: "llong",
    15: "ullong",
    16: "FILE*",
    17: "bool",
    18: "wchar",
    19: "wstring",
    20: "void*",
    21: "enum",
    22: "struct",
    23: "opaque",
    24: "stl",
    25: "BAD_REF",
}
SCALAR_FORMATS = {
    (1, 1): "b",
    (2, 1): "B",
    (4, 2): "h",
    (5, 2): "H",
    (6, 4): "i",
    (7, 4): "I",
    (8, 8): "q",
    (9, 8): "Q",
    (10, 4): "f",
    (11, 8): "d",
    (12, 4): "i",
    (13, 4): "I",
    (14, 8): "q",
    (15, 8): "Q",
    (17, 1): "?",
    (18, 4): "I",
    (21, 4): "i",
    (25, 4): "i",
}


def hexdump(data: bytes) -> str:
    lines = []
    for off in range(0, len(data), 16):
        chunk = data[off : off + 16]
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{off:08x}  {chunk.hex(' '):<47}  {text}")
    return "\n".join(lines)


def decode_value(trick_type: int, size: int, raw: bytes, order: str) -> str:
    fmt = SCALAR_FORMATS.get((trick_type, size))
    if fmt:
        return repr(struct.unpack(order + fmt, raw)[0])
    if trick_type in (1, 3):
        return repr(raw)
    if trick_type in (18, 19) and size % 4 == 0:
        chars = struct.unpack(order + f"{size // 4}I", raw)
        return repr("".join(chr(c) for c in chars))
    return raw.hex(" ")


def decode_binary(data: bytes, nonames: bool, order: str) -> list[str]:
    out = []
    pos = 0
    while pos + 12 <= len(data):
        msg_type, size, count = struct.unpack_from(order + "iii", data, pos)
        end = pos + 4 + size
        out.append(f"message type={msg_type} size={size} vars={count}")
        pos += 12
        for _ in range(count):
            name = ""
            if not nonames:
                (name_len,) = struct.unpack_from(order + "i", data, pos)
                name = data[pos + 4 : pos + 4 + name_len].decode(errors="replace")
                pos += 4 + name_len
            trick_type, vsize = struct.unpack_from(order + "ii", data, pos)
            raw = data[pos + 8 : pos + 8 + vsize]
            pos += 8 + vsize
            label = TYPE_NAMES.get(trick_type, str(trick_type))
            out.append(
                f"  {name or '-':32} {label:8} size={vsize:<5} {decode_value(trick_type, vsize, raw, order)}"
            )
        if pos != end:
            out.append(
                f"  (message ends at {end}, decoder at {pos}; rest is not a variable message)"
            )
            pos = end
    if pos < len(data):
        out.append(f"trailing {len(data) - pos} bytes:\n{hexdump(data[pos:])}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--nonames", action="store_true")
    parser.add_argument("--byteswap", action="store_true")
    args = parser.parse_args()
    data = args.path.read_bytes()
    if not data:
        print("(empty)")
        return
    if data[:1].isdigit():
        print(data.decode(errors="replace"), end="")
        return
    print(hexdump(data))
    order = ">" if args.byteswap else "<"
    try:
        print("\n".join(decode_binary(data, args.nonames, order)))
    except struct.error as e:
        print(f"(not a variable message: {e})")


if __name__ == "__main__":
    main()
