#!/usr/bin/env bash
# `quantseq-counts run` lists the run's images with `nextflow inspect` before it starts the run. That preview must not
# write run/DONE (which marks a run that ended without error) nor any other file in the output folder.
# Needs a Nextflow 25.04.8 (NXF=path, default: install's bin/nextflow).
# Usage: bash tests/workflow/test_inspect_no_done.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")/../.." && pwd)"
NXF="${NXF:-$HERE/bin/nextflow}"; T="${KEEP:-$(mktemp -d)}"; [ -n "${KEEP:-}" ] || trap 'rm -rf "$T"' EXIT; mkdir -p "$T"
python3 "$HERE/tools/make_synthetic_data.py" "$T/data" >/dev/null
PYTHONPATH="$HERE/src" python3 - "$T" <<'PY'
import sys
from quantseq_counts import settings as st, __version__
t = sys.argv[1]
s = {"package_version": __version__, "run_name": "inspect", "fastq_dir": f"{t}/data", "samples": f"{t}/data/samples.csv",
     "outdir": f"{t}/out", "reference": "custom", "fasta": f"{t}/data/genome.fa.gz", "gtf": f"{t}/data/genes.gtf.gz",
     "reference_dir": f"{t}/ref", "library": "fwd_no_umi", "min_trimmed_reads": 0}
open(f"{t}/params.yaml", "w").write(st.dump_settings(s))
PY
mkdir -p "$T/out/run"
( cd "$T/out/run" && "$NXF" inspect "$HERE/workflow/main.nf" -c "$HERE/workflow/conf/test.config" -params-file "$T/params.yaml" > "$T/inspect.json" 2> "$T/inspect.err" )
rc=$?; fail=0; ok() { echo "ok - $1"; }; ko() { echo "FAIL - $1"; fail=1; }
[ $rc -eq 0 ] && ok "nextflow inspect exits 0" || { ko "nextflow inspect exits 0"; tail -20 "$T/inspect.err"; }
grep -q '"processes"' "$T/inspect.json" && ok "inspect lists the processes" || ko "inspect lists the processes"
[ -e "$T/out/run/DONE" ] && ko "inspect writes no run/DONE" || ok "inspect writes no run/DONE"
[ $fail -eq 0 ] && echo "RESULT: PASS" || { echo "RESULT: FAIL"; exit 1; }
