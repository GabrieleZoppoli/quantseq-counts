#!/usr/bin/env bash
# The gate's logic, with a stand-in quantseq-counts that writes made-up outputs: equal for A, B and C; the
# deduplicated BAM depends on the thread config only when the sort is off (as STAR's order would make it).
set -uo pipefail
HERE="$(cd "$(dirname "$0")/../.." && pwd)"; T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/inst/bin" "$T/inst/env/bin"
ln -s "$(command -v python3)" "$T/inst/env/bin/python"; cp -R "$HERE/src" "$HERE/schema" "$HERE/workflow" "$HERE/tools" "$T/inst/"
cat > "$T/inst/bin/quantseq-counts" <<'FAKE'
#!/usr/bin/env bash
s=""; extra=""; while [ $# -gt 0 ]; do case "$1" in --settings) s="$2"; shift 2;; --extra-config) extra="$2"; shift 2;; *) shift;; esac; done
out=$(sed -n "s/^outdir: '\(.*\)'$/\1/p" "$s"); det=$(sed -n 's/^deterministic_sort: //p' "$s")
mkdir -p "$out/run/intermediate" "$out/qc"; printf 'g\t1\n' > "$out/counts.tsv"; printf 'x' > "$out/counts.rds"; printf 'q\n' > "$out/qc/samples.tsv"
printf 'r1\n' > "$out/run/intermediate/S1.sorted.bam"
if [ "$det" = false ] && [ -n "$extra" ]; then printf 'r2\n' > "$out/run/intermediate/S1.umi_dedup.sorted.bam"; else printf 'r1\n' > "$out/run/intermediate/S1.umi_dedup.sorted.bam"; fi
printf '@r\nA\n+\nI\n' | gzip -c > "$out/run/intermediate/S1_trimmed_trimmed.fq.gz"
FAKE
chmod +x "$T/inst/bin/quantseq-counts"
printf '#!/bin/sh\n[ "$1" = view ] && cat "$2"\n' > "$T/samtools"; chmod +x "$T/samtools"; export SAMTOOLS="$T/samtools"
PYTHONPATH="$HERE/src" python3 -c "
from quantseq_counts import settings as st, __version__
open('$T/base.yaml','w').write(st.dump_settings({'package_version': __version__, 'run_name': 'g', 'fastq_dir': '/x', 'samples': '/x/s.csv', 'outdir': '/x/o', 'reference_dir': '/x/r'}))"
fail=0; ok() { echo "ok - $1"; }; ko() { echo "FAIL - $1"; fail=1; }
bash "$HERE/tools/release_gate.sh" --install "$T/inst" --settings "$T/base.yaml" --out "$T/g" --runs A,C,D1,D2 > "$T/o" 2>&1; rc=$?
[ $rc -eq 0 ] && ok "gate passes: A = C, D1 differs from D2" || { ko "gate passes"; cat "$T/o"; }
grep -q $'^A_vs_C\tsame' "$T/g/gate.tsv" && grep -q $'^D1_vs_D2\tdifferent' "$T/g/gate.tsv" && ok "gate.tsv rows" || { ko "gate.tsv rows"; cat "$T/g/gate.tsv"; }
grep -q "^deterministic_sort: false" "$T/g/D2/settings.yaml" && grep -q "^keep_trimmed_fastq: true" "$T/g/A/settings.yaml" && ok "run settings derived" || ko "run settings derived"
bash "$HERE/tools/release_gate.sh" --install "$T/inst" --settings "$T/base.yaml" --out "$T/g" --runs B > "$T/o" 2>&1; rc=$?
[ $rc -eq 0 ] && grep -q $'^A_vs_B\tsame' "$T/g/gate.tsv" && ok "day-two run B compared with A" || { ko "day-two run B"; cat "$T/o"; }
# a gate whose control cannot show a difference must not pass
sed -i.bak 's/if \[ "\$det" = false \] && \[ -n "\$extra" \]/if false/' "$T/inst/bin/quantseq-counts"; rm -rf "$T/g"
bash "$HERE/tools/release_gate.sh" --install "$T/inst" --settings "$T/base.yaml" --out "$T/g" --runs A,C,D1,D2 > "$T/o" 2>&1; rc=$?
[ $rc -eq 1 ] && grep -q "control" "$T/o" && ok "control without difference: gate fails" || { ko "control without difference"; cat "$T/o"; }
[ $fail -eq 0 ] && echo "RESULT: PASS" || { echo "RESULT: FAIL"; exit 1; }
