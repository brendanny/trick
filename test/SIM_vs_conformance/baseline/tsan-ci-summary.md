# Variable server CI: tsan

| Step | Result | Time | Log |
| --- | --- | --- | --- |
| Build Trick | PASS | 10 s | `build-trick.log` |
| Build VS unit tests | PASS | 20 s | `build-unit-tests.log` |
| Unit: VariableReference_test | PASS | 0 s | `unit-VariableReference_test.log` |
| Unit: VariableReference_writeValueAscii_test | PASS | 0 s | `unit-VariableReference_writeValueAscii_test.log` |
| Unit: VariableReference_writeValueBinary_test | PASS | 0 s | `unit-VariableReference_writeValueBinary_test.log` |
| Unit: VariableServerSession_test | PASS | 5 s | `unit-VariableServerSession_test.log` |
| Unit: VariableServerSessionThread_test | PASS | 0 s | `unit-VariableServerSessionThread_test.log` |
| Unit: VariableServerListenThread_test | PASS | 22 s | `unit-VariableServerListenThread_test.log` |
| Unit: VariableServer_test | PASS | 0 s | `unit-VariableServer_test.log` |
| Harness venv | PASS | 5 s | `venv.log` |
| Build SIM_vs_conformance | PASS | 2 s | `build-conformance.log` |
| Conformance suite | PASS | 57 s | `conformance.log` |
| Known defects (informational) | 4 xfailed, 3 xpassed in 31.81s | - | - |
| Build SIM_test_varserv | PASS | 10 s | `build-varserv.log` |
| SIM_test_varserv | PASS | 123 s | `varserv.log` |

Distinct sanitizer report signatures: 33. See `sanitizer-summary.md`.
