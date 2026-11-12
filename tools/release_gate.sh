#!/usr/bin/env bash
# The release gate: fresh runs of the same data, compared object by object (tools/compare_runs.sh).
#   A   standard                      B   standard, another day (a later call with --runs B)
#   C   other thread counts (workflow/conf/threads_alt.config)
#   D1  name-then-position sort off, standard threads;  D2  sort off, other thread counts (the control)
# Passes when A = C (and A = B once B exists) and D1 differs from D2: the control shows that the comparison sees a
# change in the reads kept when the order of tied reads follows the thread count. All runs keep their BAMs and trimmed
# reads; none uses -resume. Results in OUT/gate.tsv.
# Usage: tools/release_gate.sh --install PREFIX --settings BASE.yaml --out OUT [--runs A,C,D1,D2 | --runs B]
set -uo pipefail
INST=""; BASE=""; OUT=""; RUNS="A,C,D1,D2"
while [ $# -gt 0 ]; do case "$1" in
  --install) INST="$2"; shift 2 ;; --settings) BASE="$2"; shift 2 ;; --out) OUT="$2"; shift 2 ;; --runs) RUNS="$2"; shift 2 ;;
  *) echo "unknown option $1" >&2; exit 2 ;; esac; done
[ -n "$INST" ] && [ -f "$BASE" ] && [ -n "$OUT" ] || { echo "usage: release_gate.sh --install PREFIX --settings BASE.yaml --out OUT [--runs ...]" >&2; exit 2; }
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
ALT="$INST/workflow/conf/threads_alt.config"
[ -x "$INST/env/bin/samtools" ] && export SAMTOOLS="${SAMTOOLS:-$INST/env/bin/samtools}"
for r in ${RUNS//,/ }; do
  [ -d "$OUT/$r/out" ] && { echo "$OUT/$r already holds a run: the gate needs fresh runs" >&2; exit 2; }
  mkdir -p "$OUT/$r"
  PYTHONPATH="$INST/src" "$INST/env/bin/python" - "$BASE" "$OUT/$r" "$r" <<'PY'
import sys
from pathlib import Path
from quantseq_counts import settings as st
base, d, r = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
s = st.load_settings(Path(base))
samples = Path(s["samples"]); samples = samples if samples.is_absolute() else (Path(base).parent / samples).resolve()
s.update({"run_name": f"gate_{r}", "outdir": str(d / "out"), "samples": str(samples), "keep_bams": True,
          "keep_trimmed_fastq": True, "deterministic_sort": not r.startswith("D")})
(d / "settings.yaml").write_text(st.dump_settings(s))
PY
  extra=(); case "$r" in C|D2) extra=(--extra-config "$ALT") ;; esac
  echo "== run $r started $(date '+%Y-%m-%d %H:%M %Z')"
  "$INST/bin/quantseq-counts" run --settings "$OUT/$r/settings.yaml" --yes --foreground ${extra[@]+"${extra[@]}"} > "$OUT/$r/run.out" 2>&1 \
    || { echo "run $r failed (exit $?): $OUT/$r/run.out" >&2; exit 1; }
  echo "== run $r ended $(date '+%Y-%m-%d %H:%M %Z')"
done
cmp_pair() {  # name a b expect(same|different)
  [ -d "$OUT/$2/out" ] && [ -d "$OUT/$3/out" ] || return 0
  bash "$INST/tools/compare_runs.sh" "$OUT/$2/out" "$OUT/$3/out" > "$OUT/$1.tsv"; local rc=$?
  local res; res=$([ $rc -eq 0 ] && echo same || echo different)
  printf '%s\t%s\t%s\t%s\n' "$1" "$res" "$(wc -l < "$OUT/$1.tsv" | tr -d ' ')" "$(grep -vc '^same' "$OUT/$1.tsv")"
}
{ printf 'comparison\tresult\tobjects\tnot_same\n'; cmp_pair A_vs_C A C; cmp_pair A_vs_B A B; cmp_pair D1_vs_D2 D1 D2; } > "$OUT/gate.tsv"
cat "$OUT/gate.tsv"
bad=0
grep -q $'^A_vs_C\tdifferent' "$OUT/gate.tsv" && { echo "FAIL: A and C differ (thread counts): see $OUT/A_vs_C.tsv"; bad=1; }
grep -q $'^A_vs_B\tdifferent' "$OUT/gate.tsv" && { echo "FAIL: A and B differ (another day): see $OUT/A_vs_B.tsv"; bad=1; }
if grep -q $'^D1_vs_D2\tsame' "$OUT/gate.tsv"; then
  echo "FAIL: the control (sort off, two thread counts) shows no difference, so this gate cannot show that it detects one"; bad=1; fi
[ $bad -eq 0 ] && echo "GATE: PASS" || echo "GATE: FAIL"
exit $bad
