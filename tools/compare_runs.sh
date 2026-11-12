#!/usr/bin/env bash
# Compares two output folders of quantseq-counts for the release gate: counts.tsv, counts.rds and qc/samples.tsv byte
# for byte; the alignment records (samtools view, header left out, since it holds paths and command lines) of every
# pre-deduplication and deduplicated BAM; the decompressed trimmed reads. Needs both runs made with keep_bams and
# keep_trimmed_fastq. One line per object (same / DIFFERENT / MISSING); exit 0 only when everything is the same,
# 1 when something differs, 2 when an object cannot be read (a digest is never taken of nothing).
# Usage: tools/compare_runs.sh RUN_A RUN_B      (SAMTOOLS=command overrides `samtools`)
set -uo pipefail
A="$1"; B="$2"; ST="${SAMTOOLS:-samtools}"; bad=0
md5() { if command -v md5sum >/dev/null; then md5sum | cut -c1-32; else md5 -q; fi; }
EMPTY=$(printf '' | md5)
digest() {  # kind path: the digest, or exit 2 when it cannot be computed (never a vacuous "same")
  local d
  case "$1" in
    bytes) d=$(md5 < "$2") ;;
    bam)   d=$(set -o pipefail; $ST view "$2" | md5) || d="" ;;
    fq)    d=$(set -o pipefail; gzip -cd "$2" | md5) || d="" ;;
  esac
  if [ -z "$d" ] || { [ "$1" != bytes ] && [ "$d" = "$EMPTY" ]; }; then
    echo "ERROR: cannot read $2 ($1); is samtools working (SAMTOOLS=$ST)?" >&2; exit 2; fi
  echo "$d"
}
objects() {
  for f in counts.tsv counts.rds qc/samples.tsv; do echo "bytes $f"; done
  for d in "$A" "$B"; do ( cd "$d" && ls run/intermediate/*.bam 2>/dev/null | sed "s/^/bam /"; ls run/intermediate/*.fq.gz 2>/dev/null | sed "s/^/fq /" ); done | sort -u
}
while read -r kind rel; do
  if [ ! -e "$A/$rel" ] || [ ! -e "$B/$rel" ]; then printf 'MISSING\t%s\n' "$rel"; bad=1; continue; fi
  da=$(digest "$kind" "$A/$rel") || exit 2; db=$(digest "$kind" "$B/$rel") || exit 2
  if [ "$da" = "$db" ]; then printf 'same\t%s\n' "$rel"
  else printf 'DIFFERENT\t%s\n' "$rel"; bad=1; fi
done < <(objects)
exit $bad
