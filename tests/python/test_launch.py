import os

import pytest
from pathlib import Path

from quantseq_counts import __version__, launch
from quantseq_counts import settings as st


def base(tmp_path, **kw):
    s = {"package_version": __version__, "run_name": "t", "fastq_dir": str(tmp_path / "fq"),
         "samples": "s.csv", "outdir": str(tmp_path / "out"), "reference_dir": str(tmp_path / "ref")}
    s.update(kw)
    return st.with_defaults(s)


def test_mounts_follow_symlinks(tmp_path):
    other = tmp_path / "other" / "b"; other.mkdir(parents=True)
    d = tmp_path / "data"; d.mkdir()
    (d / "a").symlink_to(other)
    target = other / "x.fastq.gz"; target.write_text("x")
    (d / "f.fastq.gz").symlink_to(target)
    m = launch.container_mounts([d / "a", d / "f.fastq.gz"])
    assert str(d) in m or str(d / "a") in m
    assert str(other.resolve()) in m
    assert len(m) == len(set(m))
    # a mount inside another is dropped
    assert not any(x != y and x.startswith(y + os.sep) for x in m for y in m)


def test_dry_run_slurm(tmp_path):
    s = base(tmp_path, executor="slurm", slurm_queue="short", slurm_account="lab1")
    rd = tmp_path / "out" / "run"
    argv = launch.nextflow_command(s, rd, Path("/opt/qc"), resume=True)
    assert argv[argv.index("-profile") + 1] == "apptainer,slurm"
    assert "-resume" in argv
    cfg = launch.run_config(s, [str(tmp_path)])
    assert "queue = 'short'" in cfg and "--account=lab1" in cfg


def test_local_limits_in_config(tmp_path):
    s = base(tmp_path, max_cpus=12, max_memory="96 GB")
    cfg = launch.run_config(s, ["/srv"])
    assert "cpus = 12" in cfg and "memory = '96 GB'" in cfg
    assert "apptainer.runOptions = '-B /srv'" in cfg


def test_udocker_env(tmp_path):
    s = base(tmp_path, engine="udocker")
    rd = tmp_path / "run"; rd.mkdir()
    env = launch.engine_env(s, rd, tmp_path / "install")
    assert env["UDOCKER_DEFAULT_EXECUTION_MODE"] == "P1"
    assert env["UDOCKER_REGISTRY"] == "https://quay.io"
    assert env["UDOCKER_DIR"] == str(tmp_path / "install" / "udocker")
    shim = rd / "shim" / "udocker.py"
    assert shim.exists() and os.access(shim, os.X_OK)
    assert str(tmp_path / "install" / "env" / "bin" / "udocker") in shim.read_text()
    assert env["PATH"].split(os.pathsep)[0] == str(rd / "shim")
    s2 = base(tmp_path, engine="udocker", udocker_dir=str(tmp_path / "ud"))
    assert launch.engine_env(s2, rd, tmp_path / "install")["UDOCKER_DIR"] == str(tmp_path / "ud")
    cfg = launch.run_config(s, ["/srv"])
    assert "udocker.runOptions = '-v /srv'" in cfg


def test_docker_mounts_in_config(tmp_path):
    cfg = launch.run_config(base(tmp_path, engine="docker"), ["/srv", "/mnt/x"])
    assert "docker.runOptions = '-v /srv:/srv -v /mnt/x:/mnt/x'" in cfg


def _fake(path, body):
    path.write_text("#!/bin/sh\n" + body); path.chmod(0o755)


def test_inspect_and_pull(tmp_path):
    inst = tmp_path / "inst"; (inst / "bin").mkdir(parents=True); (inst / "env" / "bin").mkdir(parents=True)
    _fake(inst / "bin" / "nextflow", """cat <<'J'
{"processes": [{"name": "A", "container": "quay.io/x/a:1"}, {"name": "B", "container": "c.io/lib/b:2"},
               {"name": "C", "container": "quay.io/x/a:1"}, {"name": "D", "container": null}]}
J
""")
    log = tmp_path / "calls.txt"
    _fake(inst / "env" / "bin" / "udocker", f'echo "$@" >> {log}\ncase "$2" in *b:2) [ "$1" = verify ] && exit 1;; esac\nexit 0\n')
    rd = tmp_path / "run"; rd.mkdir()
    s = base(tmp_path, engine="udocker")
    env = launch.engine_env(s, rd, inst)
    images = launch.inspect_containers(s, rd, inst, env)
    assert images == ["c.io/lib/b:2", "quay.io/x/a:1"]
    failed = launch.udocker_pull(images, env, rd)
    assert failed == ["c.io/lib/b:2"]
    calls = log.read_text().split("\n")
    assert calls[:4] == ["pull c.io/lib/b:2", "verify c.io/lib/b:2", "pull quay.io/x/a:1", "verify quay.io/x/a:1"]
    assert (rd / "images.log").exists()


def test_verify_fallback_to_blob_checksums(tmp_path):
    import hashlib
    inst = tmp_path / "inst"; (inst / "env" / "bin").mkdir(parents=True)
    _fake(inst / "env" / "bin" / "udocker", 'case "$1" in verify) exit 1;; esac\nexit 0\n')
    ud = tmp_path / "ud"
    s = base(tmp_path, engine="udocker", udocker_dir=str(ud))
    rd = tmp_path / "run"; rd.mkdir()
    env = launch.engine_env(s, rd, inst)
    blob = ud / "layers" / "blob1"; blob.parent.mkdir(parents=True); blob.write_bytes(b"layer")
    tagdir = ud / "repos" / "c.io" / "lib" / "p" / "1"; tagdir.mkdir(parents=True)
    (tagdir / ("sha256:" + hashlib.sha256(b"layer").hexdigest())).symlink_to(blob)
    assert launch.udocker_pull(["c.io/lib/p:1"], env, rd) == []
    blob.write_bytes(b"changed")
    assert launch.udocker_pull(["c.io/lib/p:1"], env, rd) == ["c.io/lib/p:1"]
    assert launch.udocker_pull(["c.io/lib/none:1"], env, rd) == ["c.io/lib/none:1"]


def test_containers_tsv(tmp_path):
    inst = tmp_path / "inst"; (inst / "bin").mkdir(parents=True)
    _fake(inst / "bin" / "nextflow", """echo 'N E X T F L O W'; cat <<'J'
{"processes": [{"name": "STAR_ALIGN", "container": "c.io/lib/star:1"}, {"name": "FASTQC", "container": "q.io/f:2"},
               {"name": "DOWNLOAD_REFERENCE", "container": null}]}
J
""")
    rd = tmp_path / "run"; rd.mkdir()
    s = base(tmp_path, engine="docker")
    procs = launch.inspect_processes(s, rd, inst, dict(os.environ))
    launch.write_containers(procs, rd)
    assert (rd / "containers.tsv").read_text() == "process\tcontainer\tdigest\nDOWNLOAD_REFERENCE\tnone (runs on the host)\t\nFASTQC\tq.io/f:2\t\nSTAR_ALIGN\tc.io/lib/star:1\t\n"


def test_run_samples_written_canonical(tmp_path):
    raw = tmp_path / "pasted.csv"
    raw.write_bytes("﻿Sample\tFASTQ\tGroup\r\nA1 \t a1.fastq.gz\tcase\r\n\r\n".encode("utf-8"))
    rd = tmp_path / "run"
    launch.write_run_files(base(tmp_path), raw, rd, ["/srv"])
    assert (rd / "samples.csv").read_text() == "sample,fastq,group\nA1,a1.fastq.gz,case\n"


def _store(ud, name, tag, config, layers):
    d = ud / "repos" / name / tag; d.mkdir(parents=True, exist_ok=True)
    import json as _j
    (d / "manifest").write_text(_j.dumps({"config": {"digest": config}, "layers": [{"digest": x} for x in layers]}))


def test_udocker_checks_pins_and_skips_present(tmp_path):
    inst = tmp_path / "inst"; (inst / "env" / "bin").mkdir(parents=True)
    log = tmp_path / "calls.txt"
    _fake(inst / "env" / "bin" / "udocker", f'echo "$@" >> {log}\nexit 0\n')
    ud = tmp_path / "ud"
    s = base(tmp_path, engine="udocker", udocker_dir=str(ud))
    rd = tmp_path / "run"; rd.mkdir()
    env = launch.engine_env(s, rd, inst)
    pins = {"biocontainers/a:1": {"config_digest": "sha256:c1", "layer_digests": "sha256:l1;sha256:l2"},
            "community.wave.seqera.io/library/b:2": {"config_digest": "sha256:c2", "layer_digests": "sha256:l3"}}
    _store(ud, "biocontainers/a", "1", "sha256:c1", ["sha256:l1", "sha256:l2"])          # present and right
    _store(ud, "community.wave.seqera.io/library/b", "2", "sha256:cX", ["sha256:l3"])    # present, wrong config
    failed = launch.udocker_pull(["biocontainers/a:1", "community.wave.seqera.io/library/b:2"], env, rd, pins)
    calls = log.read_text() if log.exists() else ""
    assert "pull biocontainers/a:1" not in calls
    assert failed == ["community.wave.seqera.io/library/b:2"]
    assert "digest" in (rd / "images.log").read_text()


def test_pins_table_loaded():
    from pathlib import Path
    pins = launch.load_pins(Path(__file__).resolve().parents[2])
    assert "biocontainers/fastqc:0.12.1--hdfd78af_0" in pins
    assert pins["biocontainers/fastqc:0.12.1--hdfd78af_0"]["digest"].startswith("sha256:")


def test_inspect_failure_is_a_message_with_its_log(tmp_path):
    # nextflow inspect failing (a broken settings file, no Java): a clear error naming the log, not a traceback
    inst = tmp_path / "inst"; (inst / "bin").mkdir(parents=True)
    _fake(inst / "bin" / "nextflow", "echo 'ERROR ~ no such param' >&2; exit 1\n")
    rd = tmp_path / "run"; rd.mkdir()
    with pytest.raises(RuntimeError, match="inspect.log"):
        launch.inspect_processes(base(tmp_path, engine="docker"), rd, inst, dict(os.environ))
    assert "no such param" in (rd / "inspect.log").read_text()
