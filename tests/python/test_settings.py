from quantseq_counts import __version__
from quantseq_counts import settings as st

TABLE_KEYS = [
    "package_version", "run_name", "fastq_dir", "samples", "outdir", "library", "reference", "fasta", "gtf",
    "reference_dir", "engine", "udocker_dir", "executor", "max_cpus", "max_memory", "slurm_queue", "slurm_account",
    "umi_pattern", "dedup_algo", "trim_adapter", "star_extra_args", "star_threads", "strand", "count_multimappers",
    "dedup_without_umi", "deterministic_sort", "keep_bams", "keep_trimmed_fastq", "min_trimmed_reads",
    "skip_qualimap", "skip_rseqc", "skip_dupradar",
]


def minimal():
    return {
        "package_version": __version__, "run_name": "study1", "fastq_dir": "/srv/fq", "samples": "samples.csv",
        "outdir": "/srv/out", "reference_dir": "/srv/ref",
    }


def test_defaults_complete():
    for k in TABLE_KEYS:
        assert k in st.SCHEMA, k
        assert "default" in st.SCHEMA[k] and st.SCHEMA[k]["help"].strip(), k
        assert st.SCHEMA[k]["group"] in ("basic", "advanced"), k
    assert set(st.SCHEMA) == set(TABLE_KEYS)


def test_standard_values():
    d = st.with_defaults(minimal())
    assert d["library"] == "fwd_umi" and d["reference"] == "ensembl_115" and d["engine"] == "apptainer"
    assert d["executor"] == "local" and d["max_cpus"] == 16 and d["max_memory"] == "160 GB"
    assert d["umi_pattern"] == "^(?P<umi_1>.{6})(?P<discard_1>.{4}).*"
    assert d["dedup_algo"] == "dir" and d["trim_adapter"] == "AGATCGGAAGAGC"
    assert d["star_extra_args"] == "--outFilterMismatchNoverLmax 0.1 --clip3pAdapterSeq AAAAAAAA"
    assert d["star_threads"] is None and d["strand"] == "forward" and d["min_trimmed_reads"] == 10000
    assert d["count_multimappers"] is False and d["deterministic_sort"] is True and d["keep_bams"] is False


def test_minimal_is_valid():
    assert st.validate(minimal()) == []


def test_missing_required():
    s = minimal(); del s["fastq_dir"]
    errs = st.validate(s)
    assert any("fastq_dir" in e for e in errs)


def test_conditionally_required():
    s = minimal(); s["reference"] = "custom"
    errs = st.validate(s)
    assert any("fasta" in e for e in errs) and any("gtf" in e for e in errs)
    s = minimal(); s["executor"] = "slurm"
    assert any("slurm_queue" in e for e in st.validate(s))


def test_enum_rejected():
    s = minimal(); s["library"] = "rev"
    errs = st.validate(s)
    assert len(errs) == 1 and "fwd_umi" in errs[0] and "fwd_no_umi" in errs[0]


def test_type_and_pattern_rejected():
    s = minimal(); s["max_cpus"] = "many"; s["run_name"] = "my run"
    errs = st.validate(s)
    assert any("max_cpus" in e for e in errs) and any("run_name" in e for e in errs)


def test_unknown_key_rejected():
    s = minimal(); s["salmon"] = True
    assert any("salmon" in e for e in st.validate(s))


def test_changes_listed():
    s = minimal(); s["strand"] = "reverse"
    assert st.changes_from_default(s) == [("strand", "forward", "reverse")]
    assert st.changes_from_default(minimal()) == []


def test_warnings():
    cases = {"strand": "reverse", "count_multimappers": True, "dedup_without_umi": True, "deterministic_sort": False}
    for k, v in cases.items():
        s = minimal(); s[k] = v
        w = st.warnings_for(s)
        assert w == [st.SCHEMA[k]["warning"]], (k, w)
    s = minimal(); s["strand"] = "unstranded"
    assert st.warnings_for(s) == [st.SCHEMA["strand"]["warning"]]
    assert st.warnings_for(minimal()) == []


def test_version_mismatch_stops():
    s = minimal(); s["package_version"] = "0.0.9"
    errs = st.validate(s)
    assert any("0.0.9" in e and __version__ in e for e in errs)
    assert st.validate(s, accept_version_change=True) == []


def test_load_settings(tmp_path):
    p = tmp_path / "settings.yaml"
    p.write_text("run_name: study1\nmax_cpus: 8\n")
    assert st.load_settings(p) == {"run_name": "study1", "max_cpus": 8}


def test_change_from_empty_default_listed():
    s = minimal(); s["star_threads"] = 8
    assert st.changes_from_default(s) == [("star_threads", None, 8)]
