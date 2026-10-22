# Variable server CI: asan

| Step | Result | Time | Log |
| --- | --- | --- | --- |
| Build Trick | PASS | 11 s | `build-trick.log` |
| Build VS unit tests | PASS | 45 s | `build-unit-tests.log` |
| Unit: VariableReference_test | PASS | 0 s | `unit-VariableReference_test.log` |
| Unit: VariableReference_writeValueAscii_test | PASS | 1 s | `unit-VariableReference_writeValueAscii_test.log` |
| Unit: VariableReference_writeValueBinary_test | PASS | 0 s | `unit-VariableReference_writeValueBinary_test.log` |
| Unit: VariableServerSession_test | PASS | 6 s | `unit-VariableServerSession_test.log` |
| Unit: VariableServerSessionThread_test | PASS | 0 s | `unit-VariableServerSessionThread_test.log` |
| Unit: VariableServerListenThread_test | PASS | 21 s | `unit-VariableServerListenThread_test.log` |
| Unit: VariableServer_test | PASS | 0 s | `unit-VariableServer_test.log` |
| Harness venv | PASS | 8 s | `venv.log` |
| Build SIM_vs_conformance | PASS | 4 s | `build-conformance.log` |
| Conformance suite | PASS | 55 s | `conformance.log` |
| Known defects (informational) | 7 xfailed in 37.14s | - | - |
| Build SIM_test_varserv | PASS | 26 s | `build-varserv.log` |
| SIM_test_varserv | PASS | 122 s | `varserv.log` |

Distinct sanitizer report signatures: 17. See `sanitizer-summary.md`.
