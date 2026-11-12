import gzip

import pytest

from quantseq_counts import samples as sm


def fastq(path, seqs, gz=True):
    body = "".join(f"@r{i}\n{s}\n+\n{'I' * len(s)}\n" for i, s in enumerate(seqs))
    if gz:
        with gzip.open(path, "wt") as f:
            f.write(body)
    else:
        path.write_text(body)


def test_reads_plain_list(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("sample,fastq,group\nA1,a1.fastq.gz,case\nB2,b2.fq.gz,\n")
    assert sm.read_samples(p) == [sm.Sample("A1", "a1.fastq.gz", "case"), sm.Sample("B2", "b2.fq.gz", None)]


@pytest.mark.parametrize("raw", [
    "﻿sample,fastq\nA1,a1.fastq.gz\nB2,b2.fastq.gz\n",
    "sample,fastq\r\nA1,a1.fastq.gz\r\nB2,b2.fastq.gz\r\n",
    "sample,fastq\nA1 , a1.fastq.gz \nB2,b2.fastq.gz\n\n\n",
    "sample\tfastq\nA1\ta1.fastq.gz\nB2\tb2.fastq.gz\n",
])
def test_excel_paste_variants(tmp_path, raw):
    p = tmp_path / "s.csv"
    p.write_bytes(raw.encode("utf-8"))
    assert [(s.name, s.fastq) for s in sm.read_samples(p)] == [("A1", "a1.fastq.gz"), ("B2", "b2.fastq.gz")]


def test_bad_name_gives_line_number(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("sample,fastq\nA1,a1.fastq.gz\nmy sample,b.fastq.gz\n")
    with pytest.raises(ValueError, match="line 3"):
        sm.read_samples(p)


def test_missing_columns(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("name,file\nA1,a1.fastq.gz\n")
    with pytest.raises(ValueError, match="sample.*fastq"):
        sm.read_samples(p)


def test_missing_and_duplicate(tmp_path):
    fastq(tmp_path / "a.fastq.gz", ["ACGT"])
    rows = [sm.Sample("A", "a.fastq.gz", None), sm.Sample("A", "b.fastq.gz", None), sm.Sample("C", "a.fastq.gz", None)]
    errors, _ = sm.check_folder(rows, tmp_path)
    assert any("b.fastq.gz" in e and "not found" in e for e in errors)
    assert any("A" in e and "twice" in e for e in errors)
    assert any("a.fastq.gz" in e and "two rows" in e for e in errors)


def test_extra_file_warns(tmp_path):
    fastq(tmp_path / "a.fastq.gz", ["ACGT"]); fastq(tmp_path / "z.fq.gz", ["ACGT"])
    (tmp_path / "notes.txt").write_text("x")
    errors, warnings = sm.check_folder([sm.Sample("A", "a.fastq.gz", None)], tmp_path)
    assert errors == [] and len(warnings) == 1 and "z.fq.gz" in warnings[0]


def test_parent_path_rejected(tmp_path):
    errors, _ = sm.check_folder([sm.Sample("A", "../x.fastq.gz", None)], tmp_path)
    assert any(".." in e for e in errors)


@pytest.mark.parametrize("gz", [True, False])
def test_probe_umi(tmp_path, gz):
    p = tmp_path / ("a.fastq.gz" if gz else "a.fastq")
    fastq(p, ["AAAAAATATAGGGG"] * 30 + ["AAAAAACCCCGGGG"] * 10, gz=gz)
    assert sm.probe_umi(p) == pytest.approx(0.75)
    assert sm.probe_umi(p, n=10) == pytest.approx(1.0)


def test_disagreement():
    assert sm.umi_disagreement("fwd_umi", 0.9) is None
    assert "UMI" in sm.umi_disagreement("fwd_umi", 0.1)
    assert sm.umi_disagreement("fwd_no_umi", 0.05) is None
    assert "UMI" in sm.umi_disagreement("fwd_no_umi", 0.8)
