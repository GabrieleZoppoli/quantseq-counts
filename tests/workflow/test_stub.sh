#!/usr/bin/env bash
# Stub run of the whole workflow on the synthetic data: every process is wired and runs its stub; checks the
# processes that must and must not be in the run. Needs a Nextflow 25.04.8 (NXF=path, default: install's bin/nextflow).
# Usage: bash tests/workflow/test_stub.sh [library]   (library: fwd_umi, default, or fwd_no_umi)
set -uo pipefail
HERE="$(cd "$(dirname "$0")/../.." && pwd)"; LIB="${1:-fwd_umi}"
NXF="${NXF:-$HERE/bin/nextflow}"; T="${KEEP:-$(mktemp -d)}"; [ -n "${KEEP:-}" ] || trap 'rm -rf "$T"' EXIT; mkdir -p "$T"
python3 "$HERE/tools/make_synthetic_data.py" "$T/data" >/dev/null
PYTHONPATH="$HERE/src" python3 - "$T" "$LIB" <<'PY'
import sys
from quantseq_counts import settings as st, __version__
t, lib = sys.argv[1], sys.argv[2]
s = {"package_version": __version__, "run_name": "stub", "fastq_dir": f"{t}/data", "samples": f"{t}/data/samples.csv",
     "outdir": f"{t}/out", "reference": "custom", "fasta": f"{t}/data/genome.fa.gz", "gtf": f"{t}/data/genes.gtf.gz",
     "reference_dir": f"{t}/ref", "library": lib, "min_trimmed_reads": 0}
open(f"{t}/params.yaml", "w").write(st.dump_settings(s))
PY
# stand-ins for the tools, which answer only the version questions of the modules (stub runs need no real tools)
mkdir -p "$T/fakebin"
for c in STAR bam_stat.py fastqc featureCounts fq gawk infer_experiment.py junction_annotation.py junction_saturation.py multiqc qualimap read_distribution.py read_duplication.py samtools trim_galore umi_tools; do
  printf '#!/bin/sh\necho "%s 0.0.0"\n' "$c" > "$T/fakebin/$c"; chmod +x "$T/fakebin/$c"; done
# the modules' version checks use GNU sed syntax; on macOS a pass-through sed stands in (stub runs only)
[ "$(uname -s)" = Darwin ] && { printf '#!/bin/sh\ncat\n' > "$T/fakebin/sed"; chmod +x "$T/fakebin/sed"; }
( cd "$T" && PATH="$T/fakebin:$PATH" "$NXF" run "$HERE/workflow/main.nf" -stub-run -c "$HERE/workflow/conf/test.config" -params-file params.yaml -w work -ansi-log false > run.log 2>&1 )
rc=$?; fail=0; ok() { echo "ok - $1"; }; ko() { echo "FAIL - $1"; fail=1; }
[ $rc -eq 0 ] && ok "stub run exits 0" || { ko "stub run exits 0"; tail -30 "$T/run.log"; }
procs="$(awk -F'\t' 'NR > 1 {sub(/ \(.*/, "", $3); n = split($3, a, ":"); print a[n]}' "$T/out/run/trace.txt" | sort -u)"
need="QUANTSEQ_SCREEN QC_TABLE MULTIQC FEATURECOUNTS_MAIN BUILD_OUTPUTS STAR_GENOMEGENERATE STAR_ALIGN SORT_NAME_THEN_POSITION TRIMGALORE FASTQC FQ_LINT SUBREAD_FEATURECOUNTS QUALIMAP_RNASEQ DUPRADAR RSEQC_READDISTRIBUTION"
[ "$LIB" = fwd_umi ] && need="$need UMITOOLS_EXTRACT UMICOLLAPSE"
for p in $need; do printf '%s\n' "$procs" | grep -qx "$p" && ok "ran $p" || ko "ran $p"; done
for p in SALMON_QUANT TXIMETA_TXIMPORT STRINGTIE_STRINGTIE SAMTOOLS_SORT; do printf '%s\n' "$procs" | grep -qx "$p" && ko "no $p" || ok "no $p"; done
if [ "$LIB" = fwd_no_umi ]; then for p in UMITOOLS_EXTRACT UMICOLLAPSE; do printf '%s\n' "$procs" | grep -qx "$p" && ko "no $p (no-UMI mode)" || ok "no $p (no-UMI mode)"; done; fi
n=$(awk -F'\t' 'NR > 1 && $3 ~ /STAR_ALIGN/' "$T/out/run/trace.txt" | wc -l | tr -d ' '); [ "$n" = 3 ] && ok "three libraries aligned" || ko "three libraries aligned ($n)"
for f in qc/samples.tsv counts.tsv counts.rds README.txt excluded.tsv run/trace.txt run/report.html run/versions.tsv; do [ -s "$T/out/$f" ] || [ -e "$T/out/$f" ] && ok "wrote $f" || ko "wrote $f"; done
for p in STAR_ALIGN DUPRADAR CUSTOM_GTFFILTER; do grep -q "^$p"$'\t' "$T/out/run/versions.tsv" && ok "versions.tsv lists $p" || ko "versions.tsv lists $p"; done
grep -q 'featureCounts -s 1 -t exon -g gene_id' "$T"/work/*/*/featurecounts.txt && ok "main counts call" || ko "main counts call"
[ $fail -eq 0 ] && echo "RESULT: PASS" || { echo "RESULT: FAIL"; exit 1; }
