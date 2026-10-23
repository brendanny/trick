#!/usr/bin/env bash
# Variable server test run: plain build or a sanitizer build.
#
#   tools/vs-ci.sh plain|asan|tsan
#
# Run it from a configured Trick tree (./configure done). It builds Trick,
# runs the variable server unit tests, the conformance suite, a soak
# (soak/vs_soak.py) and SIM_test_varserv, and writes a summary to
# vs-ci-<kind>/summary.md.
#
# Exit status:
#   plain  non-zero if any test fails
#   asan, tsan  non-zero if any test fails or any sanitizer report remains
#          after the suppressions (tools/vs-sanitizer-env.sh). Set
#          VS_CI_FAIL_ON_REPORTS=0 to summarize reports without failing.
#
# Environment:
#   VS_PYTHON            Python 3.11+ for the test harness (default: python3)
#   VS_CONF_SIM_WRAPPER  command that starts each SIM, for example
#                        "setarch x86_64 -R" for TSan on kernels with high
#                        ASLR entropy
#   VS_SOAK_MINUTES      length of the soak (default 2; CI runs 10 under tsan)
#   VS_CI_FAIL_ON_REPORTS  1 (default) to fail on sanitizer reports

set -uo pipefail

kind="${1:-}"
case "$kind" in plain|asan|tsan) ;; *) echo "usage: $0 plain|asan|tsan" >&2; exit 2 ;; esac

repo="$(cd "$(dirname "$0")/.." && pwd)"
export TRICK_HOME="$repo"
export PATH="$repo/bin:$PATH"
out="$repo/vs-ci-$kind"
rm -rf "$out" "$repo/test/SIM_vs_conformance/conformance_logs"
mkdir -p "$out" "$repo/trick_test"
export VS_SANITIZER_LOG_DIR="$out/sanitizer_logs"
if [[ "$kind" != plain ]]; then
    # shellcheck source=tools/vs-sanitizer-env.sh
    . "$repo/tools/vs-sanitizer-env.sh" "$kind"
fi
py="${VS_PYTHON:-python3}"
wrapper="${VS_CONF_SIM_WRAPPER:-}"

declare -a results=()
failures=0

step() {
    # step NAME LOGFILE COMMAND...: run COMMAND, record pass/fail.
    local name="$1" log="$2"
    shift 2
    echo "::group::$name"
    local start=$SECONDS
    "$@" > "$log" 2>&1
    local rc=$?
    tail -n 40 "$log"
    echo "::endgroup::"
    local status=PASS
    if [[ $rc -ne 0 ]]; then status="FAIL ($rc)"; failures=$((failures + 1)); fi
    results+=("| $name | $status | $((SECONDS - start)) s | \`$(basename "$log")\` |")
    return $rc
}

note() {
    results+=("| $1 | $2 | - | - |")
}

cd "$repo" || exit 2

step "Build Trick" "$out/build-trick.log" make || {
    echo "Trick did not build; stopping." >&2
    printf '%s\n' "${results[@]}"
    exit 1
}

# The rewrite's core library: no iostreams, and its unit tests.
step "No iostreams in new VS code" "$out/no-iostreams.log" "$repo/tools/vs-check-no-iostreams.sh"
step "VS core unit tests" "$out/unit-vs-core.log" make -C "$repo/trick_source/trick_utils/var_server/test" test

# The adapter's unit tests (gtest, on a real Memory Manager).
ut_dir="$repo/trick_source/sim_services/VariableServer/test"
if step "Build VS adapter tests" "$out/build-unit-tests.log" make -C "$ut_dir" VsAdapter_test; then
    step "Unit: VsAdapter_test" "$out/unit-VsAdapter_test.log" \
        bash -c "cd '$ut_dir' && ./VsAdapter_test --gtest_output=xml:'$repo/trick_test/VsAdapter_test.xml'"
fi

# Python environment for the harness.
venv="$out/venv"
step "Harness venv" "$out/venv.log" bash -c "'$py' -m venv '$venv' && '$venv/bin/pip' install -q -r '$repo/test/SIM_vs_conformance/conformance/requirements.txt'"
"$venv/bin/python" -c 'import sys; assert sys.version_info >= (3, 11), sys.version' || {
    echo "The harness needs Python 3.11 or later; set VS_PYTHON." >&2
    exit 2
}

# Conformance suite.
conf="$repo/test/SIM_vs_conformance"
if step "Build SIM_vs_conformance" "$out/build-conformance.log" bash -c "cd '$conf' && trick-CP"; then
    # Every regression test for the old server's defects, the old-checkpoint test, and the wire cases.
    step "Conformance suite" "$out/conformance.log" \
        "$venv/bin/python" -m pytest "$conf/conformance" -q -rs --run-known-defects \
        --junitxml="$repo/trick_test/SIM_vs_conformance.xml" ${wrapper:+--sim-wrapper "$wrapper"}
    # 8 clients in every mode and a checkpoint reload every 10 s.
    step "Soak (${VS_SOAK_MINUTES:-2} min)" "$out/soak.log" \
        "$venv/bin/python" "$conf/soak/vs_soak.py" --minutes "${VS_SOAK_MINUTES:-2}" ${wrapper:+--wrapper "$wrapper"}
fi

# SIM_test_varserv: modes, UDP, multicast, freeze, var_set, stdio.
varserv="$repo/test/SIM_test_varserv"
if step "Build SIM_test_varserv" "$out/build-varserv.log" bash -c "cd '$varserv' && trick-CP -t"; then
    exe="$(ls "$varserv"/T_main_*_test.exe | head -n 1)"
    step "SIM_test_varserv" "$out/varserv.log" bash -c "cd '$varserv' && timeout 600 $wrapper '$exe' RUN_test/unit_test.py"
fi

# Sanitizer summary.
reports=0
if [[ "$kind" != plain ]]; then
    # UBSan reports go to the console logs, not to VS_SANITIZER_LOG_DIR.
    "$venv/bin/python" "$repo/tools/vs-sanitizer-summary.py" "$out" "$conf/conformance_logs" \
        --repo "$repo" --out "$out/sanitizer-summary.md" > /dev/null || true
    reports=$(grep -c '^| [AUT][a-zA-Z]*: ' "$out/sanitizer-summary.md" 2>/dev/null || echo 0)
fi

{
    echo "# Variable server CI: $kind"
    echo
    echo "| Step | Result | Time | Log |"
    echo "| --- | --- | --- | --- |"
    printf '%s\n' "${results[@]}"
    if [[ "$kind" != plain ]]; then
        echo
        echo "Distinct sanitizer report signatures: $reports. See \`sanitizer-summary.md\`."
    fi
} > "$out/summary.md"
cat "$out/summary.md"
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    cat "$out/summary.md" >> "$GITHUB_STEP_SUMMARY"
    [[ -f "$out/sanitizer-summary.md" ]] && cat "$out/sanitizer-summary.md" >> "$GITHUB_STEP_SUMMARY"
fi

if [[ "$kind" != plain && ! -f "$out/sanitizer-summary.md" ]]; then
    echo "The sanitizer summary was not written; failing." >&2
    failures=$((failures + 1))
fi
if [[ "${VS_CI_FAIL_ON_REPORTS:-1}" == 1 && $reports -gt 0 ]]; then
    echo "$reports sanitizer report signature(s); see $out/sanitizer-summary.md." >&2
    failures=$((failures + 1))
fi
[[ $failures -eq 0 ]]
