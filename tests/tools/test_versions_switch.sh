#!/usr/bin/env bash
# bin/quantseq-counts follows CURRENT to a version installed beside it, and --use VERSION picks one for one call.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/../.." && pwd)"; T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
v=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$HERE/src/quantseq_counts/__init__.py")
mkdir -p "$T/p"; cp -R "$HERE/bin" "$HERE/src" "$HERE/schema" "$T/p/"
mkdir -p "$T/p/versions/9.9.9/bin"; printf '#!/bin/sh\necho "newer $*"\n' > "$T/p/versions/9.9.9/bin/quantseq-counts"; chmod +x "$T/p/versions/9.9.9/bin/quantseq-counts"
fail=0; ok() { echo "ok - $1"; }; ko() { echo "FAIL - $1"; fail=1; }
[ "$("$T/p/bin/quantseq-counts" --version)" = "quantseq-counts $v" ] && ok "no CURRENT: runs itself" || ko "no CURRENT: runs itself"
echo 9.9.9 > "$T/p/CURRENT"
[ "$("$T/p/bin/quantseq-counts" run x)" = "newer run x" ] && ok "CURRENT 9.9.9: runs that version" || ko "CURRENT 9.9.9"
[ "$("$T/p/bin/quantseq-counts" --use "$v" --version)" = "quantseq-counts $v" ] && ok "--use own version" || ko "--use own version"
"$T/p/bin/quantseq-counts" --use 7.7.7 --version > "$T/o" 2>&1; rc=$?
[ $rc -ne 0 ] && grep -q "7.7.7 is not installed" "$T/o" && ok "--use a missing version fails" || ko "--use a missing version fails"
[ $fail -eq 0 ] && echo "RESULT: PASS" || { echo "RESULT: FAIL"; exit 1; }
