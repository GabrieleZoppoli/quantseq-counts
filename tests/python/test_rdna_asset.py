"""The 45S sequence of the rRNA check: GenBank U13369.1 bases 1-13,314, unchanged."""
import hashlib
from pathlib import Path

FA = Path(__file__).resolve().parents[2] / "workflow" / "assets" / "rdna_45s.fa"


def test_rdna_45s_fasta():
    text = FA.read_text()
    assert hashlib.md5(text.encode()).hexdigest() == "5ee382b84a2f64fb8f5cefaa5692731f"
    head, *lines = text.splitlines()
    seq = "".join(lines)
    assert head.startswith(">U13369.1:1-13314 ") and len(seq) == 13314 and set(seq) <= set("ACGT")
    # the mature rRNAs start where GenBank puts them (1-based): 18S at 3,657, 5.8S at 6,623, 28S at 7,935
    assert seq[3656:3676] == "TACCTGGTTGATCCTGCCAG"
    assert seq[6622:6642] == "CGACTCTTAGCGGTGGATCA"
    assert seq[7934:7954] == "CGCGACCTCAGATCAGACGT"
