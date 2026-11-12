#!/usr/bin/env bash
# Installs the working copy into a throwaway prefix and checks the three things a helper needs.
# Usage: bash tests/install/test_install.sh [PREFIX]   (default: a new temporary folder, removed afterwards)
set -uo pipefail
HERE="$(cd "$(dirname "$0")/../.." && pwd)"
if [ $# -ge 1 ]; then P="$1"; else P="$(mktemp -d)/qc"; trap 'rm -rf "$(dirname "$P")"' EXIT; fi
v=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$HERE/src/quantseq_counts/__init__.py")
fail=0; ok() { echo "ok - $1"; }; ko() { echo "FAIL - $1"; fail=1; }
bash "$HERE/install.sh" --prefix "$P" > "$P.install.log" 2>&1 && ok "install.sh exits 0" || { ko "install.sh exits 0"; tail -20 "$P.install.log"; }
out="$("$P/bin/quantseq-counts" --version 2>&1)"; [ "$out" = "quantseq-counts $v" ] && ok "quantseq-counts --version" || ko "quantseq-counts --version ($out)"
out="$("$P/bin/nextflow" -version 2>&1)"; printf '%s' "$out" | grep -q "version 25.04.8" && ok "nextflow 25.04.8" || ko "nextflow 25.04.8 ($out)"
"$P/env/bin/python" -c "import yaml" && ok "python with PyYAML from the lock" || ko "python with PyYAML"
if [ "$(uname -s)" = Linux ]; then UDOCKER_DIR="$P/udocker" "$P/env/bin/udocker" --help >/dev/null 2>&1 && ok "udocker present" || ko "udocker present"; fi
[ "$(cat "$P/VERSION" 2>/dev/null)" = "$v" ] && ok "VERSION file" || ko "VERSION file"
( cd "$P" && "$P/env/bin/python" -m pytest -q -p no:cacheprovider tests/python > "$P.pytest.log" 2>&1 ) && ok "unit tests pass with the installed Python" || { ko "unit tests"; tail -5 "$P.pytest.log"; }
[ $fail -eq 0 ] && echo "RESULT: PASS" || { echo "RESULT: FAIL"; exit 1; }
