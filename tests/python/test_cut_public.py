import gzip
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "cut_test_data.py"


def test_cut(tmp_path):
    fq = tmp_path / "in.fastq.gz"
    with gzip.open(fq, "wt") as f:
        for i in range(1, 2001):
            f.write(f"@SRR1.{i} {i} length=8\nACGTACGT\n+\nIIIIIIII\n")
    # aligned names as they come out of the run: UMI-tools appends _UMI to the first token
    (tmp_path / "aligned.txt").write_text("".join(f"SRR1.{i}_ACGTAC\n" for i in range(1, 2001, 4)))
    out = tmp_path / "cut.fastq.gz"
    args = [sys.executable, str(SCRIPT), "--fastq", str(fq), "--aligned", str(tmp_path / "aligned.txt"),
            "--max-reads", "400", "--other-share", "0.05", "--seed", "7", "--out", str(out)]
    subprocess.run(args, check=True)
    names = [l.split()[0][1:] for i, l in enumerate(gzip.open(out, "rt")) if i % 4 == 0]
    nums = [int(n.split(".")[1]) for n in names]
    assert len(names) == 400 and nums == sorted(nums)
    aligned = sum(1 for n in nums if n % 4 == 1)
    assert 320 <= aligned <= 375  # a quarter aligned, 5% of the rest: about 87% of the kept reads
    out2 = tmp_path / "cut2.fastq.gz"
    subprocess.run(args[:-1] + [str(out2)], check=True)
    assert out.read_bytes() == out2.read_bytes()
