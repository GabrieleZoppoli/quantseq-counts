import os
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
