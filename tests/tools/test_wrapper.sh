#!/usr/bin/env bash
# bin/quantseq-counts runs the package from its own folder, through a link too.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/../.." && pwd)"; T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
v=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$HERE/src/quantseq_counts/__init__.py")
out="$(bash "$HERE/bin/quantseq-counts" --version 2>&1)"; [ "$out" = "quantseq-counts $v" ] || { echo "FAIL direct: $out"; exit 1; }
ln -s "$HERE/bin/quantseq-counts" "$T/qc"; out="$("$T/qc" --version 2>&1)"; [ "$out" = "quantseq-counts $v" ] || { echo "FAIL link: $out"; exit 1; }
echo "RESULT: PASS"
