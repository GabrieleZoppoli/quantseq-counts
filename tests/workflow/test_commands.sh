#!/usr/bin/env bash
# A real run of the synthetic data through `quantseq-counts run --foreground`, then every row of expected_args.tsv
# checked against the executed scripts (.command.sh) of its process. Needs an installation and a container engine.
# Usage: bash tests/workflow/test_commands.sh INSTALL_PREFIX ENGINE [WORKDIR] [LIBRARY] [EXECUTOR]
#   ENGINE: udocker, docker, apptainer; LIBRARY: fwd_umi (default) or fwd_no_umi; EXECUTOR: local (default) or slurm
set -uo pipefail
HERE="$(cd "$(dirname "$0")/../.." && pwd)"; INST="$1"; ENGINE="$2"
T="${3:-$(mktemp -d)}"; mkdir -p "$T"; LIB="${4:-fwd_umi}"; EXE="${5:-local}"
nu=""; [ "$LIB" = fwd_no_umi ] && nu="--no-umi"
"$INST/env/bin/python" "$HERE/tools/make_synthetic_data.py" "$T/data" $nu >/dev/null
PYTHONPATH="$HERE/src" "$INST/env/bin/python" - "$T" "$ENGINE" "$LIB" "$EXE" <<'PY'
import os, sys
from quantseq_counts import settings as st, __version__
t, eng, lib, exe = sys.argv[1:5]
s = {"package_version": __version__, "run_name": "commands", "fastq_dir": f"{t}/data", "samples": "data/samples.csv",
     "outdir": f"{t}/out", "reference": "custom", "fasta": f"{t}/data/genome.fa.gz", "gtf": f"{t}/data/genes.gtf.gz",
     "reference_dir": f"{t}/ref", "engine": eng, "max_cpus": int(os.environ.get("MAX_CPUS", 8)), "max_memory": os.environ.get("MAX_MEMORY", "32 GB"), "min_trimmed_reads": 0,
     "library": lib, "executor": exe, "slurm_queue": "debug" if exe == "slurm" else None}
open(f"{t}/settings.yaml", "w").write(st.dump_settings(s))
PY
"$INST/bin/quantseq-counts" run --settings "$T/settings.yaml" --yes --foreground > "$T/run.out" 2>&1; rc=$?
fail=0; ok() { echo "ok - $1"; }; ko() { echo "FAIL - $1"; fail=1; }
[ $rc -eq 0 ] && ok "run exits 0" || { ko "run exits 0 ($rc)"; tail -40 "$T/out/run/nextflow.log"; }
tail -n +2 "$HERE/tests/workflow/expected_args.tsv" | while IFS=$'\t' read -r proc kind text _src; do
  if [ "$LIB" = fwd_no_umi ] && { [ "$proc" = UMITOOLS_EXTRACT ] || [ "$proc" = UMICOLLAPSE ]; }; then
    grep -q "^### name: '$proc (" "$T"/out/work/*/*/.command.run 2>/dev/null && echo "FAIL - $proc ran in the no-UMI mode" || echo "ok - no $proc in the no-UMI mode"
    continue; fi
  scripts=$(grep -l "^### name: '\(.*:\)\{0,1\}$proc (" "$T"/out/work/*/*/.command.run 2>/dev/null | sed 's/\.command\.run$/.command.sh/')
  [ -n "$scripts" ] || { echo "FAIL - $proc ran"; continue; }
  bad=0; for s in $scripts; do if grep -qF -- "$text" "$s"; then [ "$kind" = absent ] && bad=1; else [ "$kind" = contains ] && bad=1; fi; done
  [ $bad -eq 0 ] && echo "ok - $proc $kind: $text" || echo "FAIL - $proc $kind: $text"
done > "$T/args.txt"
cat "$T/args.txt"; grep -q '^FAIL' "$T/args.txt" && fail=1
[ $fail -eq 0 ] && echo "RESULT: PASS" || { echo "RESULT: FAIL"; exit 1; }
