#!/usr/bin/env bash
# The layout two updates produce: ROOT (0.1.0), ROOT/versions/0.2.0, ROOT/versions/0.3.0, CURRENT = 0.3.0.
# Every installed version is reachable from any of them with --use; only ROOT follows CURRENT.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/../.." && pwd)"; T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkv() { mkdir -p "$1"; cp -R "$HERE/bin" "$HERE/src" "$HERE/schema" "$1/"; sed -i.bak "s/^__version__ = .*/__version__ = \"$2\"/" "$1/src/quantseq_counts/__init__.py"; }
mkv "$T/root" 0.1.0; mkv "$T/root/versions/0.2.0" 0.2.0; mkv "$T/root/versions/0.3.0" 0.3.0; echo 0.3.0 > "$T/root/CURRENT"
fail=0
t() { local want="$1"; shift; out="$("$@" --version 2>&1)"; [ "$out" = "quantseq-counts $want" ] && echo "ok - $* -> $want" || { echo "FAIL - $* gave '$out', not $want"; fail=1; }; }
t 0.3.0 "$T/root/bin/quantseq-counts"
t 0.2.0 "$T/root/bin/quantseq-counts" --use 0.2.0
t 0.1.0 "$T/root/bin/quantseq-counts" --use 0.1.0
t 0.3.0 "$T/root/versions/0.3.0/bin/quantseq-counts"
t 0.2.0 "$T/root/versions/0.3.0/bin/quantseq-counts" --use 0.2.0
t 0.1.0 "$T/root/versions/0.3.0/bin/quantseq-counts" --use 0.1.0
t 0.3.0 "$T/root/versions/0.2.0/bin/quantseq-counts" --use 0.3.0
[ $fail -eq 0 ] && echo "RESULT: PASS" || { echo "RESULT: FAIL"; exit 1; }
