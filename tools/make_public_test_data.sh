#!/usr/bin/env bash
# Rebuilds tests/data/public/ from the archives: downloads the first 2,000,000 reads of each library listed in
# tests/data/public/SOURCES.tsv and Ensembl 115 chromosome 22 with its genes (checked against Ensembl's checksums),
# runs quantseq-counts on them against chromosome 22 (alignments kept), and keeps, in file order, the reads aligned
# there plus 5% of the others (seed 20261112), at most 100,000 per library (tools/cut_test_data.py).
# Usage: tools/make_public_test_data.sh --install PREFIX --work DIR [--engine udocker|docker|apptainer]
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"; INST=""; WORK=""; ENGINE=apptainer
while [ $# -gt 0 ]; do case "$1" in --install) INST="$2"; shift 2;; --work) WORK="$2"; shift 2;; --engine) ENGINE="$2"; shift 2;; *) exit 2;; esac; done
[ -n "$INST" ] && [ -n "$WORK" ] || { echo "usage: make_public_test_data.sh --install PREFIX --work DIR [--engine E]" >&2; exit 2; }
PUB="$HERE/tests/data/public"; E=https://ftp.ensembl.org/pub/release-115
mkdir -p "$WORK/raw" "$WORK/ref" "$PUB/reference"
cd "$WORK/ref"
f=Homo_sapiens.GRCh38.dna.chromosome.22.fa.gz; [ -s $f ] || curl -fsSL -o $f $E/fasta/homo_sapiens/dna/$f
g=Homo_sapiens.GRCh38.115.gtf.gz; [ -s $g ] || curl -fsSL -o $g $E/gtf/homo_sapiens/$g
curl -fsSL -o CHECKSUMS.dna $E/fasta/homo_sapiens/dna/CHECKSUMS; curl -fsSL -o CHECKSUMS.gtf $E/gtf/homo_sapiens/CHECKSUMS
bash "$HERE/workflow/bin/check_ensembl_sum.sh" CHECKSUMS.dna $f; bash "$HERE/workflow/bin/check_ensembl_sum.sh" CHECKSUMS.gtf $g
cp $f "$PUB/reference/chr22.fa.gz"
gzip -cd $g | awk -F'\t' '/^#/ || $1 == "22"' | gzip -n -c > "$PUB/reference/chr22.gtf.gz"
cd "$WORK/raw"
tail -n +2 "$PUB/SOURCES.tsv" | while IFS=$'\t' read -r run library _rest; do
  [ -s $run.head.fastq.gz ] && continue
  p="vol1/fastq/${run:0:6}/0${run: -2}/$run/$run.fastq.gz"
  curl -fsS --max-time 1800 "https://ftp.sra.ebi.ac.uk/$p" | gzip -cd 2>/dev/null | head -8000000 | gzip -n -c > $run.head.fastq.gz || true
done
for lib in fwd_umi fwd_no_umi; do
  R="$WORK/run_$lib"; mkdir -p "$R"
  { echo "sample,fastq,group"; awk -F'\t' -v l=$lib 'NR > 1 && $2 == l {print $1 "," $1 ".head.fastq.gz,"}' "$PUB/SOURCES.tsv"; } > "$R/samples.csv"
  PYTHONPATH="$INST/src" "$INST/env/bin/python" - "$R" "$WORK" "$PUB" "$lib" "$ENGINE" <<'PY'
import sys
from quantseq_counts import settings as st, __version__
r, w, pub, lib, eng = sys.argv[1:6]
open(f"{r}/settings.yaml", "w").write(st.dump_settings({"package_version": __version__, "run_name": f"cut_{lib}",
    "fastq_dir": f"{w}/raw", "samples": f"{r}/samples.csv", "outdir": f"{r}/out", "reference": "custom",
    "fasta": f"{pub}/reference/chr22.fa.gz", "gtf": f"{pub}/reference/chr22.gtf.gz", "reference_dir": f"{w}/refidx",
    "library": lib, "engine": eng, "keep_bams": True, "max_cpus": 8, "max_memory": "32 GB", "min_trimmed_reads": 0}))
PY
  [ -s "$R/out/counts.tsv" ] || "$INST/bin/quantseq-counts" run --settings "$R/settings.yaml" --yes --foreground
  for b in "$R"/out/run/intermediate/*.sorted.bam; do
    case "$b" in *umi_dedup*|*posdedup*) continue;; esac
    s=$(basename "$b" .sorted.bam)
    "$INST/env/bin/samtools" view -F 2308 "$b" | cut -f1 > "$WORK/$s.aligned.txt"
    "$INST/env/bin/python" "$HERE/tools/cut_test_data.py" --fastq "$WORK/raw/$s.head.fastq.gz" --aligned "$WORK/$s.aligned.txt" \
      --max-reads 100000 --other-share 0.05 --seed 20261112 --out "$PUB/$s.fastq.gz"
  done
done
ls -la "$PUB" "$PUB/reference"
