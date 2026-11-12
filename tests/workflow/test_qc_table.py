import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "workflow" / "bin" / "qc_table.py"

STAR = """                                 Number of input reads |	{inp}
                      Uniquely mapped reads number |	{uni}
           Number of reads mapped to multiple loci |	{multi}
           Number of reads mapped to too many loci |	0
"""
TRIM = "{n} sequences processed in total\nSequences removed because they became shorter than the length cutoff of 20 bp:\t{short} (0.1%)\n"
FLAG = "{d} + 0 primary mapped (100.00% : N/A)\n"
SCREEN_H = "library\treads\tmean_length\tumi_with_n\ttata_exact\tpolyA8_any\tadapter12_any\n"


def setup(tmp, umi=True, s2_reads=900000):
    d = tmp / "in"; d.mkdir()
    for s, n in (("S1", 1000000), ("S2", s2_reads)):
        (d / f"{s}.Log.final.out").write_text(STAR.format(inp=n - 1000, uni=int(n * 0.8), multi=int(n * 0.1)))
        (d / f"{s}_trimmed.fastq.gz_trimming_report.txt").write_text(TRIM.format(n=n, short=1000))
        if umi:
            (d / f"{s}.umi_dedup.sorted.bam.flagstat").write_text(FLAG.format(d=int(n * 0.5)))
    (d / "screen.tsv").write_text(SCREEN_H + "S1\t1000000\t75.0\t1000\t950000\t200000\t30000\nS2\t%d\t75.0\t500\t40000\t1\t1\n" % s2_reads)
    (d / "featurecounts.txt.summary").write_text(
        "Status\tS1.bam\tS2.bam\nAssigned\t400000\t100\nUnassigned_MultiMapping\t50000\t20\nUnassigned_Ambiguity\t10000\t5\nUnassigned_NoFeatures\t40000\t30\n")
    (d / "thresholds.json").write_text(json.dumps({"min_assigned_reads": 1000000 // 10, "min_unique_share": 0.5,
                                                   "min_umi_spacer_share": 0.5}))
    (d / "changes.tsv").write_text("setting\tstandard\tthis_run\nstrand\tforward\treverse\nkeep_bams\tfalse\ttrue\n")
    (d / "excluded.tsv").write_text("sample\treason\nS9\tfewer than 10000 reads after trimming (5)\n")
    return d


def run(d, umi=True):
    out = d.parent / "out"
    subprocess.run([sys.executable, str(SCRIPT), "--dir", str(d), "--library", "fwd_umi" if umi else "fwd_no_umi",
                    "--thresholds", str(d / "thresholds.json"), "--changes", str(d / "changes.tsv"),
                    "--excluded", str(d / "excluded.tsv"), "--out", str(out)], check=True)
    rows = [l.split("\t") for l in (out / "samples.tsv").read_text().splitlines()]
    return out, [dict(zip(rows[0], r)) for r in rows[1:]]


def test_stage_counts(tmp_path):
    _, rows = run(setup(tmp_path))
    s1 = rows[0]
    assert s1["library"] == "S1" and s1["raw"] == "1000000" and s1["trimmed"] == "999000"
    assert s1["aligned_unique"] == "800000" and s1["aligned_multi"] == "100000" and s1["after_dedup"] == "500000"
    assert s1["counted"] == "400000" and s1["share_multimapping"] == "0.1000" and s1["share_ambiguous"] == "0.0200"
    assert s1["umi_spacer_share"] == "0.9500" and s1["flag"] == "pass" and s1["flag_reason"] == ""


def test_flag_reasons(tmp_path):
    _, rows = run(setup(tmp_path))
    s2 = rows[1]
    assert s2["flag"] == "flagged"
    assert "counted 100 < 100000" in s2["flag_reason"] and "UMI spacer in 4.4% of reads < 50.0%" in s2["flag_reason"]


def test_no_umi_mode(tmp_path):
    _, rows = run(setup(tmp_path, umi=False), umi=False)
    assert rows[0]["after_dedup"] == "" and "UMI spacer" not in rows[1]["flag_reason"]


def test_first_page(tmp_path):
    out, _ = run(setup(tmp_path))
    html = (out / "summary_mqc.html").read_text()
    assert "1 of 2 libraries passed" in html and "S2" in html
    assert "strand" in html and "reverse" in html and "keep_bams" in html
    assert "S9" in html and "fewer than 10000" in html


def test_first_page_standard(tmp_path):
    d = setup(tmp_path); (d / "changes.tsv").write_text("setting\tstandard\tthis_run\n")
    out, _ = run(d)
    assert "the standard settings" in (out / "summary_mqc.html").read_text()
