import yaml

from quantseq_counts import settings as st


def test_basic_then_advanced():
    groups = [e["group"] for e in st.SCHEMA.values()]
    assert groups == sorted(groups, key=lambda g: g != "basic")


def test_dump_roundtrip():
    s = st.with_defaults({"run_name": "x", "trim_adapter": "AGATCGGAAGAGC", "slurm_account": "it's"})
    assert yaml.safe_load(st.dump_settings(s)) == s
