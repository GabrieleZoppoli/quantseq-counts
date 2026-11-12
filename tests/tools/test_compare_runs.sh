#!/usr/bin/env bash
# tools/compare_runs.sh on made-up output folders; a stand-in samtools prints a "BAM" file's lines without its header.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/../.." && pwd)"; T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
printf '#!/bin/sh\n[ "$1" = view ] && grep -v "^@" "$2"\n' > "$T/samtools"; chmod +x "$T/samtools"; export SAMTOOLS="$T/samtools"
mk() { mkdir -p "$1/run/intermediate" "$1/qc"; printf 'gene_id\tS1\nG1\t5\n' > "$1/counts.tsv"; printf 'x' > "$1/counts.rds"
  printf 'library\tcounted\nS1\t5\n' > "$1/qc/samples.tsv"
  printf '@PG\tID:STAR\tCL:%s\nr1\t0\tchr1\t100\n' "$1" > "$1/run/intermediate/S1.sorted.bam"
  printf '@PG\tID:x\tCL:%s\nr1\t0\tchr1\t100\n' "$1" > "$1/run/intermediate/S1.umi_dedup.sorted.bam"
  printf '@r1\nACGT\n+\nIIII\n' | gzip -c > "$1/run/intermediate/S1_trimmed_trimmed.fq.gz"; }
fail=0; ok() { echo "ok - $1"; }; ko() { echo "FAIL - $1"; fail=1; }
mk "$T/a"; mk "$T/b"
bash "$HERE/tools/compare_runs.sh" "$T/a" "$T/b" > "$T/o"; rc=$?
[ $rc -eq 0 ] && ok "equal runs: exit 0 (BAM headers with different paths ignored)" || { ko "equal runs: exit 0"; cat "$T/o"; }
grep -q "same.*S1.umi_dedup.sorted.bam" "$T/o" && grep -q "same.*S1_trimmed_trimmed.fq.gz" "$T/o" && ok "every object listed" || ko "every object listed"
printf 'gene_id\tS1\nG1\t6\n' > "$T/b/counts.tsv"
bash "$HERE/tools/compare_runs.sh" "$T/a" "$T/b" > "$T/o"; rc=$?
[ $rc -eq 1 ] && grep -q "DIFFERENT.*counts.tsv" "$T/o" && ok "a changed count: exit 1 naming counts.tsv" || ko "a changed count"
mk "$T/b"; printf '@PG\nr2\t0\tchr1\t100\n' > "$T/b/run/intermediate/S1.umi_dedup.sorted.bam"
bash "$HERE/tools/compare_runs.sh" "$T/a" "$T/b" > "$T/o"; rc=$?
[ $rc -eq 1 ] && grep -q "DIFFERENT.*S1.umi_dedup.sorted.bam" "$T/o" && ok "a different kept read: exit 1" || ko "a different kept read"
rm "$T/b/run/intermediate/S1.sorted.bam"
bash "$HERE/tools/compare_runs.sh" "$T/a" "$T/b" > "$T/o"; rc=$?
[ $rc -eq 1 ] && grep -q "MISSING.*S1.sorted.bam" "$T/o" && ok "a missing file: exit 1" || ko "a missing file"
mk "$T/b"; printf '@PG\nr1\n' > "$T/b/run/intermediate/S2.sorted.bam"
bash "$HERE/tools/compare_runs.sh" "$T/a" "$T/b" > "$T/o"; rc=$?
[ $rc -eq 1 ] && grep -q "MISSING.*S2.sorted.bam" "$T/o" && ok "a file only in the second run: exit 1" || ko "a file only in the second run"
[ $fail -eq 0 ] && echo "RESULT: PASS" || { echo "RESULT: FAIL"; exit 1; }
