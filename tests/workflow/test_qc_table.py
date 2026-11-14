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
                                                   "min_umi_spacer_share": 0.5,
                                                   "max_umi_spacer_share_no_umi": 0.05}))
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
    assert "only 100 reads counted on genes, fewer than the minimum of 100,000" in s2["flag_reason"]
    assert ("UMI spacer (TATA after the 6-nt UMI) in only 4.4% of reads, fewer than the minimum of 50.0%"
            in s2["flag_reason"])


def test_no_umi_mode(tmp_path):
    _, rows = run(setup(tmp_path, umi=False), umi=False)
    assert rows[0]["after_dedup"] == "" and "UMI spacer" not in rows[1]["flag_reason"]


def test_first_page(tmp_path):
    out, _ = run(setup(tmp_path))
    html = (out / "summary_mqc.html").read_text()
    assert "1 of 2 libraries passed" in html and "S2" in html
    assert "section_name: 'Lay summary'" in html and "biologist" not in html
    assert "kept and counted" in html
    assert "strand" in html and "reverse" in html and "keep_bams" in html
    assert "S9" in html and "fewer than 10000" in html


def test_first_page_standard(tmp_path):
    d = setup(tmp_path); (d / "changes.tsv").write_text("setting\tstandard\tthis_run\n")
    out, _ = run(d)
    assert "the standard settings" in (out / "summary_mqc.html").read_text()


def test_prefix_names_read_their_own_report(tmp_path):
    d = tmp_path / "in"; d.mkdir()
    for s, n in (("P1", 1000), ("P1_T2", 5000)):
        (d / f"{s}.Log.final.out").write_text(STAR.format(inp=n, uni=n // 2, multi=0))
        (d / f"{s}_trimmed.fastq.gz_trimming_report.txt").write_text(TRIM.format(n=n, short=0))
        (d / f"{s}.umi_dedup.sorted.bam.flagstat").write_text(FLAG.format(d=n // 4))
    # P1_T2's report listed first, as some file systems do
    (d / "screen.tsv").write_text(SCREEN_H + "P1\t1000\t75\t0\t900\t0\t0\nP1_T2\t5000\t75\t0\t4500\t0\t0\n")
    (d / "featurecounts.txt.summary").write_text("Status\tP1.bam\tP1_T2.bam\nAssigned\t10\t20\n")
    (d / "thresholds.json").write_text("{}")
    (d / "changes.tsv").write_text("setting\tstandard\tthis_run\n")
    _, rows = run(d)
    assert {r["library"]: r["trimmed"] for r in rows} == {"P1": "1000", "P1_T2": "5000"}


RRNA = "library\tinput\trrna_45s\tunique_other\tmulti_other\tmt_rrna\n{lib}\t{inp}\t{r}\t{u}\t{m}\t{mt}\n"


def add_rrna(d, lib="S1", inp=999000, r=300000, u=500000, m=99000, mt=20000):
    (d / f"{lib}.rrna.tsv").write_text(RRNA.format(lib=lib, inp=inp, r=r, u=u, m=m, mt=mt))


def test_rrna_shares_of_trimmed_reads(tmp_path):
    d = setup(tmp_path); add_rrna(d)
    _, rows = run(d)
    s1 = rows[0]
    assert s1["rrna_45s_share"] == "0.3003" and s1["mt_rrna_share"] == "0.0200"


def test_rrna_missing_is_na(tmp_path):
    # rrna_check off (custom reference): no <lib>.rrna.tsv, the columns read NA
    d = setup(tmp_path); add_rrna(d, lib="S1")
    _, rows = run(d)
    assert rows[1]["rrna_45s_share"] == "NA" and rows[1]["mt_rrna_share"] == "NA"


def test_rrna_columns_never_flag(tmp_path):
    d = setup(tmp_path); add_rrna(d, r=900000, u=50000, m=40000)
    _, rows = run(d)
    assert "rRNA" not in rows[0]["flag_reason"]


def test_rrna_chart_classes_add_up(tmp_path):
    d = setup(tmp_path); add_rrna(d)
    out, _ = run(d)
    lines = [l for l in (out / "read_classes_mqc.tsv").read_text().splitlines() if not l.startswith("#")]
    head = lines[0].split("\t")
    assert head == ["Sample", "45S rRNA", "Aligned once, not rRNA", "Aligned to several places, not rRNA", "Not aligned"]
    s1 = dict(zip(head, lines[1].split("\t")))
    assert s1 == {"Sample": "S1", "45S rRNA": "300000", "Aligned once, not rRNA": "500000",
                  "Aligned to several places, not rRNA": "99000", "Not aligned": "100000"}
    assert len(lines) == 2  # S2 has no rRNA file: no bar
    assert "plot_type: 'bargraph'" in (out / "read_classes_mqc.tsv").read_text()


def test_rrna_no_chart_without_files(tmp_path):
    out, _ = run(setup(tmp_path))
    assert not (out / "read_classes_mqc.tsv").exists()


def test_rrna_classes_inconsistent_fail(tmp_path):
    # classes larger than the input: an error, never a negative bar
    d = setup(tmp_path); add_rrna(d, r=900000, u=500000, m=0)
    out = d.parent / "out"
    p = subprocess.run([sys.executable, str(SCRIPT), "--dir", str(d), "--library", "fwd_umi",
                        "--thresholds", str(d / "thresholds.json"), "--changes", str(d / "changes.tsv"),
                        "--excluded", str(d / "excluded.tsv"), "--out", str(out)], capture_output=True, text=True)
    assert p.returncode != 0 and "S1" in p.stderr


def test_mt_rrna_na_when_gtf_has_none(tmp_path):
    # a custom GTF without Mt_rRNA genes: the rRNA check writes NA for mt_rrna
    d = setup(tmp_path); add_rrna(d, mt="NA")
    _, rows = run(d)
    assert rows[0]["mt_rrna_share"] == "NA" and rows[0]["rrna_45s_share"] == "0.3003"


def test_unique_share_reason_and_rrna_in_lay_summary(tmp_path):
    # a library whose uniquely aligned share is low because of rRNA: the reason says it plainly, and the lay
    # summary adds the 45S rRNA share as context (samples.tsv keeps the reason alone)
    d = setup(tmp_path)
    (d / "S1.Log.final.out").write_text(STAR.format(inp=999000, uni=400000, multi=300000))
    add_rrna(d, r=450000, u=400000, m=100000)
    out, rows = run(d)
    assert rows[0]["flag_reason"] == ("only 40.0% of trimmed reads aligned to a single place in the genome, "
                                      "fewer than the minimum of 50.0%")
    html = (out / "summary_mqc.html").read_text()
    assert "45S rRNA: 45.0% of trimmed reads" in html


def test_multiqc_names_qualimap_by_library():
    # Qualimap reads the name-sorted BAM <lib>.namesorted.bam; MultiQC must strip the suffix so that each library
    # has one row in the general statistics
    cfg = (ROOT / "workflow" / "assets" / "multiqc_config.yml").read_text()
    assert "extra_fn_clean_exts" in cfg and "'.namesorted'" in cfg


def test_no_umi_library_with_umi_spacer_is_flagged(tmp_path):
    # no-UMI mode: TATA at bases 7-10 in more than 5% of reads means the library looks like a UMI library
    # (S1 95%: flagged; S2 4.4%: not for this reason)
    _, rows = run(setup(tmp_path, umi=False), umi=False)
    assert rows[0]["flag"] == "flagged"
    assert rows[0]["flag_reason"] == ("looks like a UMI library: UMI spacer (TATA after the 6-nt UMI) in 95.0% of "
                                      "reads, more than the maximum of 5.0% for a library without UMIs")
    assert "looks like a UMI library" not in rows[1]["flag_reason"]


def test_umi_mode_ignores_no_umi_maximum(tmp_path):
    _, rows = run(setup(tmp_path))
    assert rows[0]["flag"] == "pass"


def test_shipped_thresholds():
    th = json.loads((ROOT / "schema" / "qc_thresholds.json").read_text())
    assert th["max_umi_spacer_share_no_umi"] == 0.05 and th["min_assigned_reads"] == 500000
