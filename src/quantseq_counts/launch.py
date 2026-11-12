"""From checked settings to a Nextflow command: the run's files, its configuration, its environment, its start."""

import json
import os
import shlex
import subprocess
from pathlib import Path

from . import __version__
from . import settings as st

PROFILE_MOUNT = {"apptainer": "-B {p}", "udocker": "-v {p}", "docker": "-v {p}:{p}"}


def container_mounts(paths: list[Path]) -> list[str]:
    """Folders the containers must see: each folder (or a file's folder) as given and as its link target."""
    found = []
    for p in map(Path, paths):
        here = p.absolute()
        found.append(here if here.is_dir() else here.parent)
        real = p.resolve()
        found.append(real if real.is_dir() else real.parent)
    out = []
    for d in sorted({str(x) for x in found}, key=len):
        if not any(d == o or d.startswith(o.rstrip(os.sep) + os.sep) for o in out):
            out.append(d)
    return sorted(out)


def run_config(s: dict, mounts: list[str]) -> str:
    eng = s["engine"]
    opts = " ".join(PROFILE_MOUNT[eng].format(p=m) for m in mounts)
    lines = [f"// Written by quantseq-counts {__version__} for run {s['run_name']}; do not edit, edit settings.yaml.",
             f"{eng}.runOptions = '{opts}'",
             "process {",
             f"    resourceLimits = [ cpus: {s['max_cpus']}, memory: '{s['max_memory']}' ]"]
    if s["executor"] == "slurm":
        lines.append("    executor = 'slurm'")
        lines.append(f"    queue = '{s['slurm_queue']}'")
        if s.get("slurm_account"):
            lines.append(f"    clusterOptions = '--account={s['slurm_account']}'")
    lines.append("}")
    if s["executor"] == "local":
        lines += ["executor {", "    name = 'local'", f"    cpus = {s['max_cpus']}", f"    memory = '{s['max_memory']}'", "}"]
    return "\n".join(lines) + "\n"


def nextflow_command(s: dict, run_dir: Path, install: Path, resume: bool) -> list[str]:
    profile = s["engine"] + (",slurm" if s["executor"] == "slurm" else "")
    argv = [str(install / "bin" / "nextflow"), "run", str(install / "workflow" / "main.nf"),
            "-c", str(run_dir / "run.config"), "-params-file", str(run_dir / "settings.yaml"),
            "-profile", profile, "-w", str(Path(s["outdir"]) / "work"), "-ansi-log", "false"]
    return argv + (["-resume"] if resume else [])


def engine_env(s: dict, run_dir: Path, install: Path) -> dict:
    env = dict(os.environ)
    env["NXF_HOME"] = str(install / "nxf")
    env["NXF_OPTS"] = env.get("NXF_OPTS", "-Xms1g -Xmx4g")
    if s["engine"] == "udocker":
        shim_dir = run_dir / "shim"
        shim_dir.mkdir(parents=True, exist_ok=True)
        shim = shim_dir / "udocker.py"
        shim.write_text(f"#!/usr/bin/env bash\nexec {shlex.quote(str(install / 'env' / 'bin' / 'udocker'))} \"$@\"\n")
        shim.chmod(0o755)
        env["UDOCKER_DEFAULT_EXECUTION_MODE"] = "P1"
        env["UDOCKER_REGISTRY"] = "https://quay.io"
        env["UDOCKER_DIR"] = s.get("udocker_dir") or str(install / "udocker")
        env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
    return env


def _cell(v) -> str:
    return "" if v is None else ("true" if v is True else "false" if v is False else str(v))


def write_run_files(s: dict, samples_file: Path, run_dir: Path, mounts: list[str]) -> dict:
    """Writes run/settings.yaml (every setting, as run), run/samples.csv, run/changes.tsv, run/run.config."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "samples.csv").write_bytes(Path(samples_file).read_bytes())
    as_run = st.with_defaults(s)
    as_run["samples"] = str(run_dir / "samples.csv")
    (run_dir / "settings.yaml").write_text(st.dump_settings(as_run))
    rows = ["setting\tstandard\tthis_run"] + [f"{k}\t{_cell(d)}\t{_cell(v)}" for k, d, v in st.changes_from_default(as_run)]
    (run_dir / "changes.tsv").write_text("\n".join(rows) + "\n")
    (run_dir / "run.config").write_text(run_config(as_run, mounts))
    return as_run


def start(argv: list[str], env: dict, run_dir: Path) -> int:
    log = open(run_dir / "nextflow.log", "ab")
    p = subprocess.Popen(argv, env=env, cwd=run_dir, stdout=log, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    (run_dir / "pid").write_text(f"{p.pid}\n")
    (run_dir / "command.json").write_text(json.dumps(argv) + "\n")
    return p.pid
