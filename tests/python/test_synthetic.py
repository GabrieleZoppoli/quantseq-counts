import gzip
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def make(out):
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_synthetic_data.py"), str(out)], check=True)


def test_deterministic(tmp_path):
    make(tmp_path / "a"); make(tmp_path / "b")
    for f in sorted((tmp_path / "a").iterdir()):
        assert hashlib.md5(f.read_bytes()).hexdigest() == hashlib.md5((tmp_path / "b" / f.name).read_bytes()).hexdigest(), f.name


def test_contents(tmp_path):
    make(tmp_path)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["S1.fastq.gz", "S2.fastq.gz", "S3.fastq.gz", "genes.gtf.gz", "genome.fa.gz", "samples.csv"]
    with gzip.open(tmp_path / "S1.fastq.gz", "rt") as f:
        seqs = [l.strip() for i, l in enumerate(f) if i % 4 == 1]
    assert len(seqs) >= 5000
    assert sum(s[6:10] == "TATA" for s in seqs) / len(seqs) > 0.95
    gtf = gzip.open(tmp_path / "genes.gtf.gz", "rt").read()
    assert 'gene_biotype "protein_coding"' in gtf and "\texon\t" in gtf and 'transcript_id "' in gtf
