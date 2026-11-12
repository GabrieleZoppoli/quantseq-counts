#!/usr/bin/env bash
# Compares two output folders of quantseq-counts for the release gate: counts.tsv, counts.rds and qc/samples.tsv byte
# for byte; the alignment records (samtools view, header left out, since it holds paths and command lines) of every
# pre-deduplication and deduplicated BAM; the decompressed trimmed reads. Needs both runs made with keep_bams and
# keep_trimmed_fastq. One line per object (same / DIFFERENT / MISSING); exit 0 only when everything is the same.
# Usage: tools/compare_runs.sh RUN_A RUN_B      (SAMTOOLS=command overrides `samtools`)
set -uo pipefail
A="$1"; B="$2"; ST="${SAMTOOLS:-samtools}"; bad=0
md5() { if command -v md5sum >/dev/null; then md5sum | cut -c1-32; else md5 -q; fi; }
digest() {  # kind path
  case "$1" in
    bytes) md5 < "$2" ;;
    bam)   $ST view "$2" | md5 ;;
    fq)    gzip -cd "$2" | md5 ;;
  esac
}
objects() {
  for f in counts.tsv counts.rds qc/samples.tsv; do echo "bytes $f"; done
  for d in "$A" "$B"; do ( cd "$d" && ls run/intermediate/*.bam 2>/dev/null | sed "s/^/bam /"; ls run/intermediate/*.fq.gz 2>/dev/null | sed "s/^/fq /" ); done | sort -u
}
while read -r kind rel; do
  if [ ! -e "$A/$rel" ] || [ ! -e "$B/$rel" ]; then printf 'MISSING\t%s\n' "$rel"; bad=1; continue; fi
  if [ "$(digest "$kind" "$A/$rel")" = "$(digest "$kind" "$B/$rel")" ]; then printf 'same\t%s\n' "$rel"
  else printf 'DIFFERENT\t%s\n' "$rel"; bad=1; fi
done < <(objects)
exit $bad
