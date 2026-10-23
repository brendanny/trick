#!/usr/bin/env bash
# Fail if variable server rewrite code uses iostreams.
#
#   tools/vs-check-no-iostreams.sh [compiler]
#
# Checks two things in the new variable server code (not in tests, which may
# use iostreams through GoogleTest):
#   1. no #include of an iostreams header, and no std::cout, std::cerr,
#      std::clog, string or file streams;
#   2. no header pulls an iostreams header in indirectly: each header in
#      include/trick/vs is preprocessed alone and the result is searched.
#
# Old variable server code is not checked; the rewrite deletes it.

set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
cxx="${1:-${CXX:-c++}}"
cd "$repo"

dirs=(include/trick/vs trick_source/trick_utils/var_server)
headers='iostream|istream|ostream|sstream|fstream|iomanip|streambuf|strstream|syncstream|spanstream'
uses='std::(cout|cerr|clog|cin|endl|(i|o)?stringstream|(i|o)?fstream|(i|o)?stream)([^[:alnum:]_]|$)'

failed=0
# A while loop, not mapfile: macOS ships bash 3.2.
files=()
while IFS= read -r f; do
    files+=("$f")
done < <( (find "${dirs[@]}" -type f \( -name '*.cpp' -o -name '*.hh' -o -name '*.h' \) \
    -not -path '*/test/*' -not -path '*/testing/*'
    # The adapter (Phase 4) lives beside the old server in libtrick; its files start with "Vs".
    find trick_source/sim_services/VariableServer -maxdepth 1 -type f -name 'Vs*.cpp') | sort)

if out=$(grep -nE "^[[:space:]]*#[[:space:]]*include[[:space:]]*<(${headers})>" "${files[@]}"); then
    echo "iostream headers included:"
    echo "$out"
    failed=1
fi
if out=$(grep -nE "$uses" "${files[@]}"); then
    echo "iostream objects used:"
    echo "$out"
    failed=1
fi

for h in $(find include/trick/vs -name '*.hh' -not -path '*/testing/*' | sort); do
    if "$cxx" -std=c++17 -x c++ -E -H -Iinclude -Itrick_source "$h" -o /dev/null 2>&1 \
        | grep -E "^\.+ .*/(${headers})$" > /dev/null; then
        echo "$h includes an iostreams header indirectly:"
        "$cxx" -std=c++17 -x c++ -E -H -Iinclude -Itrick_source "$h" -o /dev/null 2>&1 | grep -E "^\.+ .*/(${headers})$" | head -5
        failed=1
    fi
done

if [[ $failed -ne 0 ]]; then
    echo "The variable server rewrite does not use iostreams (rewrite plan, Constraints)." >&2
    exit 1
fi
echo "No iostreams in ${#files[@]} variable server files."
