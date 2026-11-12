from quantseq_counts import selftest


def test_equal(tmp_path):
    a = tmp_path / "a.tsv"; a.write_text("gene_id\tgene_name\tgene_biotype\tS1\tS2\nG1\tX\tp\t5\t0\nG2\t\tl\t1\t2\n")
    assert selftest.compare_counts(a, a) == (True, "identical: 2 genes, 2 libraries")


def test_first_difference_named(tmp_path):
    a = tmp_path / "a.tsv"; b = tmp_path / "b.tsv"
    a.write_text("gene_id\tgene_name\tgene_biotype\tS1\tS2\nG1\tX\tp\t5\t0\nG2\t\tl\t1\t2\n")
    b.write_text("gene_id\tgene_name\tgene_biotype\tS1\tS2\nG1\tX\tp\t5\t0\nG2\t\tl\t1\t3\n")
    ok, msg = selftest.compare_counts(a, b)
    assert not ok and "G2" in msg and "S2" in msg and "2" in msg and "3" in msg


def test_shape_difference(tmp_path):
    a = tmp_path / "a.tsv"; b = tmp_path / "b.tsv"
    a.write_text("gene_id\tS1\nG1\t5\n"); b.write_text("gene_id\tS1\tS2\nG1\t5\t1\n")
    ok, msg = selftest.compare_counts(a, b)
    assert not ok and "libraries" in msg


def test_settings_for_bundled_data(tmp_path):
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    s, samples = selftest.selftest_settings(root, "fwd_umi", "docker", tmp_path, 4, "14 GB")
    assert s["library"] == "fwd_umi" and s["engine"] == "docker" and s["reference"] == "custom"
    assert s["fasta"].endswith("tests/data/public/reference/chr22.fa.gz") and s["max_cpus"] == 4
    assert samples.read_text().splitlines() == ["sample,fastq,group", "SRR13248213,SRR13248213.fastq.gz,",
                                                "SRR13248206,SRR13248206.fastq.gz,", "SRR13248224,SRR13248224.fastq.gz,"]


def test_cli_test_compares(tmp_path, monkeypatch, capsys):
    from quantseq_counts import cli
    def fake_run(argv, ask=None):
        s = dict(l.split(": ", 1) for l in open(argv[argv.index("--settings") + 1]).read().splitlines() if l and not l.startswith("#"))
        out = tmp_path / s["outdir"].strip("'").split("/")[-1]
        out.mkdir(parents=True, exist_ok=True)
        (out / "counts.tsv").write_text("gene_id\tS\nG\t1\n")
        return 0
    monkeypatch.setattr(selftest, "_run", fake_run)
    monkeypatch.setattr(selftest, "expected_file", lambda root, lib: tmp_path / f"exp_{lib}.tsv")
    (tmp_path / "exp_fwd_umi.tsv").write_text("gene_id\tS\nG\t1\n")
    (tmp_path / "exp_fwd_no_umi.tsv").write_text("gene_id\tS\nG\t2\n")
    rc = cli.main(["test", "--engine", "docker", "--workdir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1 and "fwd_umi: identical" in out and "fwd_no_umi: first difference" in out
