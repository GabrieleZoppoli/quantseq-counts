#!/usr/bin/env bash
# Test of tools/leak_check.sh on a throwaway repository with a made-up pattern file.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/../.." && pwd)"; LC="$HERE/tools/leak_check.sh"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
fail=0; ok() { echo "ok - $1"; }; ko() { echo "FAIL - $1"; fail=1; }
printf 'AB[0-9]{3}\nsecret-host\n' > "$T/patterns.txt"
R="$T/repo"; mkdir -p "$R"; cd "$R"; git init -q; git config user.email t@t; git config user.name t
echo "clean text" > a.txt; git add a.txt; git commit -qm one
out="$(bash "$LC" --patterns "$T/patterns.txt" "$R")"; rc=$?
[ $rc -eq 0 ] && ok "clean tree passes" || ko "clean tree passes (rc $rc: $out)"
echo "sample AB123 here" > x.txt
out="$(bash "$LC" --patterns "$T/patterns.txt" "$R")"; rc=$?
[ $rc -eq 1 ] && ok "planted identifier fails" || ko "planted identifier fails (rc $rc)"
printf '%s\n' "$out" | grep -qx 'x.txt:1:AB\[0-9\]{3}' && ok "reports file:line:pattern" || ko "reports file:line:pattern (got: $out)"
git add x.txt; git commit -qm two; git rm -q x.txt; git commit -qm three
out="$(bash "$LC" --patterns "$T/patterns.txt" "$R")"; rc=$?
[ $rc -eq 0 ] && ok "deleted file: tree clean" || ko "deleted file: tree clean (rc $rc)"
out="$(bash "$LC" --patterns "$T/patterns.txt" --history "$R")"; rc=$?
[ $rc -eq 1 ] && ok "history catches the deleted file" || ko "history catches the deleted file (rc $rc)"
printf '%s\n' "$out" | grep -q 'x.txt' && ok "history names the file" || ko "history names the file (got: $out)"
echo "the secret-host was here" > ".hidden"; out="$(bash "$LC" --patterns "$T/patterns.txt" "$R")"; rc=$?
[ $rc -eq 1 ] && ok "hidden files scanned" || ko "hidden files scanned (rc $rc)"
rm .hidden; bash "$LC" "$R" >/dev/null 2>&1; rc=$?
[ $rc -eq 2 ] && ok "missing pattern file is an error" || ko "missing pattern file is an error (rc $rc)"
[ $fail -eq 0 ] && echo "RESULT: PASS" || { echo "RESULT: FAIL"; exit 1; }
