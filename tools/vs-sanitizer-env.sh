# shellcheck shell=bash
# Source this file to build and run Trick with sanitizers, for the variable
# server rewrite (Phase 0 baseline and every later phase).
#
#   . tools/vs-sanitizer-env.sh asan    # AddressSanitizer + UndefinedBehaviorSanitizer
#   . tools/vs-sanitizer-env.sh tsan    # ThreadSanitizer
#
# Then configure and build Trick, build the SIM, and run the tests in the
# same shell. Trick's makefiles append to TRICK_CFLAGS, TRICK_CXXFLAGS and
# TRICK_LDFLAGS from the environment. Do not pass these on the make command
# line: that replaces the makefiles' own flags.
#
# Reports go to $VS_SANITIZER_LOG_DIR (default: ./sanitizer_logs), one file
# per process, so a report from the SIM is not lost in its console output.

_vs_kind="${1:-}"
_vs_repo="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"

case "$_vs_kind" in
    asan)
        # -fsanitize-recover=address lets a SIM keep running after a report,
        # so one run shows every defect it reaches, not only the first.
        _vs_flags="-fsanitize=address,undefined -fsanitize-recover=address -fno-omit-frame-pointer -fno-sanitize=vptr -g -O1"
        ;;
    tsan)
        _vs_flags="-fsanitize=thread -fno-omit-frame-pointer -g -O1"
        ;;
    *)
        echo "usage: . tools/vs-sanitizer-env.sh asan|tsan" >&2
        return 2 2>/dev/null || exit 2
        ;;
esac

export VS_SANITIZER="$_vs_kind"
export VS_SANITIZER_LOG_DIR="${VS_SANITIZER_LOG_DIR:-$PWD/sanitizer_logs}"
mkdir -p "$VS_SANITIZER_LOG_DIR"

export TRICK_CFLAGS="${TRICK_CFLAGS:+$TRICK_CFLAGS }$_vs_flags"
export TRICK_CXXFLAGS="${TRICK_CXXFLAGS:+$TRICK_CXXFLAGS }$_vs_flags"
export TRICK_LDFLAGS="${TRICK_LDFLAGS:+$TRICK_LDFLAGS }$_vs_flags"

# Leak reports are off: Trick allocates for the life of the process, and the
# rewrite's leak work is checked by unit tests, not by whole-SIM runs.
export ASAN_OPTIONS="detect_leaks=0:abort_on_error=0:halt_on_error=0:log_path=$VS_SANITIZER_LOG_DIR/asan"
export UBSAN_OPTIONS="print_stacktrace=1:halt_on_error=0:log_path=$VS_SANITIZER_LOG_DIR/ubsan"
export TSAN_OPTIONS="halt_on_error=0:second_deadlock_stack=1:history_size=4:log_path=$VS_SANITIZER_LOG_DIR/tsan:suppressions=$_vs_repo/tools/vs-tsan.supp"

unset _vs_kind _vs_flags _vs_repo
