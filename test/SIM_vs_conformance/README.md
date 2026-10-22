# SIM_vs_conformance

Byte-level conformance suite for the variable server. It records the exact
bytes that the server sends for a fixed set of command scripts. The
variable server rewrite must send the same bytes, except for the changes
that the rewrite plan lists as intentional.

## Run

Build Trick, then build the SIM and run the suite from the repository root.
The suite needs Python 3.11 or later and pytest.

```bash
(cd test/SIM_vs_conformance && trick-CP)
python3 -m venv .venv && .venv/bin/pip install -r test/SIM_vs_conformance/conformance/requirements.txt
.venv/bin/python -m pytest test/SIM_vs_conformance/conformance
```

The suite starts the SIM on a free port, runs each case on a new
connection, and stops the SIM at the end. SIM output goes to
`conformance_logs/`.

| Option | Use |
| --- | --- |
| `--update-goldens` | Write new golden files. Each case runs twice and must give the same bytes both times. |
| `--run-known-defects` | Also run `test_known_defects.py`. Each test starts its own SIM. |
| `--sim-exe PATH` | Use this SIM executable, for example a sanitizer build. |
| `--sim-wrapper CMD` | Start the SIM through a command, for example `setarch -R`. |

## Files

| File | Contents |
| --- | --- |
| `S_define`, `models/conformance/` | One variable for each Trick type, arrays, pointers, units, bitfields, STL. Values are fixed after `default_data`. |
| `RUN_conformance/input.py` | Allows connections, sets the port, keeps the SIM in freeze so time stays at 0. |
| `conformance/cases.py` | The command script for each case. |
| `conformance/goldens/*.bin` | Reply bytes from the old server, one file per case. |
| `conformance/test_wire.py` | Compares replies with the goldens. |
| `conformance/test_beacon.py` | Checks the 12-field multicast beacon on both groups. |
| `conformance/test_known_defects.py` | Defects in the old server. Expected to fail until the rewrite fixes them. |
| `conformance/dump_golden.py` | Prints a golden file as text or decoded binary. |

## How a case is captured

1. Connect and send `trick.var_pause()` plus the case commands in one send.
2. Wait 0.25 s, so the server reads the next send separately.
3. Send `trick.var_ascii()` and `trick.var_send_once("conf.vars.end_marker")`.
4. Read until the marker reply `5\t@@vs-conformance-end@@\n`. The bytes before it are the case reply.
5. Check that nothing arrives for 0.3 s after the marker.

## Limits

* The goldens are for 64-bit little-endian Linux. Binary replies use native
  byte order and type sizes.
* No golden holds a raw address. Pointer variables in binary mode, and whole
  STL containers in either mode, send heap addresses, so cases read only
  NULL pointers, pointed-to values and indexed STL elements.
* Cases that trigger a known memory defect are not in the goldens. They are
  in `test_known_defects.py`.
* Copy modes, write modes, timing, UDP and multicast sessions are not in
  this suite. `SIM_test_varserv` covers them.
