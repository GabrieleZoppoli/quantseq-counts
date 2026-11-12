#!/usr/bin/env bash
# A real run of the synthetic data through `quantseq-counts run --foreground`, then every row of expected_args.tsv
# checked against the executed scripts (.command.sh) of its process. Needs an installation and a container engine.
# Usage: bash tests/workflow/test_commands.sh INSTALL_PREFIX ENGINE [WORKDIR]   (ENGINE: udocker, docker, apptainer)
set -uo pipefail
HERE="$(cd "$(dirname "$0")/../.." && pwd)"; INST="$1"; ENGINE="$2"
T="${3:-$(mktemp -d)}"; mkdir -p "$T"
"$INST/env/bin/python" "$HERE/tools/make_synthetic_data.py" "$T/data" >/dev/null
PYTHONPATH="$HERE/src" "$INST/env/bin/python" - "$T" "$ENGINE" <<'PY'
import sys
from quantseq_counts import settings as st, __version__
t, eng = sys.argv[1], sys.argv[2]
s = {"package_version": __version__, "run_name": "commands", "fastq_dir": f"{t}/data", "samples": "data/samples.csv",
     "outdir": f"{t}/out", "reference": "custom", "fasta": f"{t}/data/genome.fa.gz", "gtf": f"{t}/data/genes.gtf.gz",
     "reference_dir": f"{t}/ref", "engine": eng, "max_cpus": 8, "max_memory": "32 GB", "min_trimmed_reads": 0}
open(f"{t}/settings.yaml", "w").write(st.dump_settings(s))
PY
"$INST/bin/quantseq-counts" run --settings "$T/settings.yaml" --yes --foreground > "$T/run.out" 2>&1; rc=$?
fail=0; ok() { echo "ok - $1"; }; ko() { echo "FAIL - $1"; fail=1; }
[ $rc -eq 0 ] && ok "run exits 0" || { ko "run exits 0 ($rc)"; tail -40 "$T/out/run/nextflow.log"; }
tail -n +2 "$HERE/tests/workflow/expected_args.tsv" | while IFS=$'\t' read -r proc kind text _src; do
  scripts=$(grep -l "^### name: '\(.*:\)\{0,1\}$proc (" "$T"/out/work/*/*/.command.run 2>/dev/null | sed 's/\.command\.run$/.command.sh/')
  [ -n "$scripts" ] || { echo "FAIL - $proc ran"; continue; }
  bad=0; for s in $scripts; do if grep -qF -- "$text" "$s"; then [ "$kind" = absent ] && bad=1; else [ "$kind" = contains ] && bad=1; fi; done
  [ $bad -eq 0 ] && echo "ok - $proc $kind: $text" || echo "FAIL - $proc $kind: $text"
done > "$T/args.txt"
cat "$T/args.txt"; grep -q '^FAIL' "$T/args.txt" && fail=1
[ $fail -eq 0 ] && echo "RESULT: PASS" || { echo "RESULT: FAIL"; exit 1; }
