#!/usr/bin/env bash
# With Docker and Apptainer every process's image is pinned to the digest of workflow/assets/containers.tsv; with
# udocker images are named by tag (and checked against the same digests by `run`). Needs Nextflow 25.04.8 (NXF=...).
set -uo pipefail
HERE="$(cd "$(dirname "$0")/../.." && pwd)"; NXF="${NXF:-$HERE/bin/nextflow}"; T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
PYTHONPATH="$HERE/src" python3 - "$T" "$HERE" <<'PY'
import sys
from quantseq_counts import settings as st, __version__
t, h = sys.argv[1:3]
for lib in ("fwd_umi", "fwd_no_umi"):
    open(f"{t}/{lib}.yaml", "w").write(st.dump_settings({"package_version": __version__, "run_name": "p", "fastq_dir": f"{h}/tests/data/synthetic",
        "samples": f"{h}/tests/data/synthetic/samples.csv", "outdir": f"{t}/out", "reference": "custom", "fasta": f"{h}/tests/data/synthetic/genome.fa.gz",
        "gtf": f"{h}/tests/data/synthetic/genes.gtf.gz", "reference_dir": f"{t}/ref", "library": lib, "dedup_without_umi": lib == "fwd_no_umi", "rrna_check": True}))
PY
unpinned() {  # images (stdin) not pinned to a digest of the table
  local i d
  while read -r i; do
    if [[ "$i" == *@sha256:* ]]; then d="${i#*@}"; printf '%s\n' "$digests" | grep -qx "$d" || echo "$i"; else echo "$i"; fi
  done
}
fail=0; ok() { echo "ok - $1"; }; ko() { echo "FAIL - $1"; fail=1; }
digests="$(cut -f5 "$HERE/workflow/assets/containers.tsv" | tail -n +2 | sort -u)"
for prof in docker apptainer udocker; do for lib in fwd_umi fwd_no_umi; do
  ( cd "$T" && "$NXF" inspect "$HERE/workflow/main.nf" -params-file $lib.yaml -profile $prof > $prof.$lib.json 2> $prof.$lib.err ) || { ko "inspect $prof $lib"; cat "$T/$prof.$lib.err"; continue; }
  imgs="$(python3 -c "import json,sys; [print(p.get('container') or '') for p in json.load(open(sys.argv[1]))['processes']]" "$T/$prof.$lib.json" | grep .)"
  if [ $prof = udocker ]; then
    printf '%s\n' "$imgs" | grep -q '@sha256:' && ko "$prof $lib: images by tag" || ok "$prof $lib: images by tag"
  else
    bad=$(printf '%s\n' "$imgs" | unpinned)
    [ -z "$bad" ] && ok "$prof $lib: every image pinned to a listed digest" || { ko "$prof $lib: not pinned: $bad"; }
  fi
done; done
[ $fail -eq 0 ] && echo "RESULT: PASS" || { echo "RESULT: FAIL"; exit 1; }
