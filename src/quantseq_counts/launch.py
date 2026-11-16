"""From checked settings to a Nextflow command: the run's files, its configuration, its environment, its start."""

import json
import os
import shlex
import subprocess
from pathlib import Path

from . import __version__
from . import samples as samples_mod
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
             f"    resourceLimits = [ cpus: {s['max_cpus']}, memory: '{s['max_memory']}', time: '{s['max_time']}' ]"]
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
    if s["engine"] == "apptainer":
        # images pulled once and kept in the installation (Nextflow's default is each run's work folder)
        env.setdefault("NXF_APPTAINER_CACHEDIR", str(install / "apptainer"))
    return env


def _cell(v) -> str:
    return "" if v is None else ("true" if v is True else "false" if v is False else str(v))


def write_run_files(s: dict, samples_file: Path, run_dir: Path, mounts: list[str]) -> dict:
    """Writes run/settings.yaml (every setting, as run), run/samples.csv, run/changes.tsv, run/run.config."""
    run_dir.mkdir(parents=True, exist_ok=True)
    # the run reads this copy (Nextflow, R, bug-report): written from the parsed rows, in one plain form
    rows = samples_mod.read_samples(Path(samples_file))
    (run_dir / "samples.csv").write_text("sample,fastq,group\n" + "".join(f"{r.name},{r.fastq},{r.group or ''}\n" for r in rows))
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


def run_foreground(argv: list[str], env: dict, run_dir: Path) -> int:
    """Runs Nextflow attached (for job scripts and tests), its output in run/nextflow.log; returns its exit status."""
    (run_dir / "command.json").write_text(json.dumps(argv) + "\n")
    with open(run_dir / "nextflow.log", "ab") as log:
        return subprocess.call(argv, env=env, cwd=run_dir, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)


def inspect_containers(s: dict, run_dir: Path, install: Path, env: dict) -> list[str]:
    """The container images the run will use, from `nextflow inspect`, sorted and without repeats."""
    return sorted({c for _p, c in inspect_processes(s, run_dir, install, env) if c})


def write_containers(procs: list[tuple[str, str | None]], run_dir: Path, pins: dict | None = None) -> None:
    pins = pins or {}
    def dig(c):
        if not c:
            return ""
        if "@sha256:" in c:
            return c.split("@", 1)[1]
        return pins.get(_norm(c), {}).get("digest", "")
    rows = ["process\tcontainer\tdigest"] + [f"{p}\t{c or 'none (runs on the host)'}\t{dig(c)}" for p, c in sorted(procs)]
    (run_dir / "containers.tsv").write_text("\n".join(rows) + "\n")


def inspect_processes(s: dict, run_dir: Path, install: Path, env: dict) -> list[tuple[str, str | None]]:
    """(process, container) for every process of the run, from `nextflow inspect`."""
    argv = [str(install / "bin" / "nextflow"), "inspect", str(install / "workflow" / "main.nf"),
            "-c", str(run_dir / "run.config"), "-params-file", str(run_dir / "settings.yaml"),
            "-profile", s["engine"]]
    r = subprocess.run(argv, env=env, cwd=run_dir, capture_output=True, text=True)
    out = r.stdout
    try:
        if r.returncode != 0:
            raise ValueError(f"exit status {r.returncode}")
        data = json.loads(out[out.index("{"):])
    except ValueError as e:
        (run_dir / "inspect.log").write_text(f"$ {' '.join(argv)}\n{out}\n{r.stderr}")
        raise RuntimeError(f"nextflow could not read the run's settings ({e}): see {run_dir / 'inspect.log'}") from None
    return [(p["name"].split(":")[-1], p.get("container")) for p in data["processes"]]


def _norm(img: str) -> str:
    return img[len("quay.io/"):] if img.startswith("quay.io/") else img


def load_pins(install: Path) -> dict:
    """workflow/assets/containers.tsv: for each image (without 'quay.io/'), its pinned digest, config and layers."""
    f = Path(install) / "workflow" / "assets" / "containers.tsv"
    rows = [l.split("\t") for l in f.read_text().splitlines()]
    return {_norm(r[0]): dict(zip(rows[0], r)) for r in rows[1:]}


def _stored_matches(udocker_dir: Path, img: str, pin: dict) -> bool | None:
    """None when the image is not in udocker's store; else whether its manifest has the pinned config and layers."""
    name, _, tag = img.rpartition(":")
    mf = udocker_dir / "repos" / name / tag / "manifest"
    if not mf.exists():
        return None
    try:
        m = json.loads(mf.read_text())
        layers = ";".join(l["digest"] for l in m.get("layers", []))
        return m["config"]["digest"] == pin["config_digest"] and layers == pin["layer_digests"]
    except (ValueError, KeyError):
        return False


def udocker_pull(images: list[str], env: dict, run_dir: Path, pins: dict | None = None) -> list[str]:
    """Pulls and verifies each image in turn with udocker (concurrent pulls by Nextflow fail), unless it is already in
    the store with the pinned digests; checks every image against its pin; returns the failures."""
    ud = env["PATH"].split(os.pathsep)[0] + "/udocker.py"
    ud = ud if os.access(ud, os.X_OK) else "udocker"
    store = Path(env.get("UDOCKER_DIR", ""))
    failed = []
    with open(run_dir / "images.log", "a") as log:
        for img in images:
            pin = (pins or {}).get(_norm(img))
            if pin and _stored_matches(store, img, pin):
                log.write(f"{img}: in the store with the pinned digests; not pulled\n")
                continue
            r = subprocess.run([ud, "pull", img], env=env, capture_output=True, text=True)
            log.write(f"pull {img}: exit {r.returncode}\n{r.stdout[-2000:]}{r.stderr[-2000:]}\n")
            ok = r.returncode == 0
            if ok:
                r = subprocess.run([ud, "verify", img], env=env, capture_output=True, text=True)
                log.write(f"verify {img}: exit {r.returncode}\n{r.stdout[-2000:]}{r.stderr[-2000:]}\n")
                if r.returncode != 0:
                    # udocker cannot verify some images (pruned layers); check each stored layer against its digest
                    ok = _blobs_match(Path(env["UDOCKER_DIR"]), img)
                    log.write(f"layer checksums of {img} against their digests: {'all equal' if ok else 'FAIL'}\n")
            if ok and pin:
                ok = bool(_stored_matches(store, img, pin))
                log.write(f"{img}: config and layer digests {'equal to' if ok else 'DIFFERENT from'} the pinned image\n")
            if not ok:
                failed.append(img)
    return failed


def docker_pull(images: list[str], env: dict, run_dir: Path) -> list[str]:
    """Pulls each image Docker does not have yet, one at a time, before the run, so that a daemon that cannot reach
    the registry is reported at once and not as a failed step. The images are named by their pinned digests
    (workflow/conf/containers.config), so Docker checks each one as it pulls it. Stops at the first failure,
    which it returns."""
    import shutil
    failed = []
    with open(run_dir / "images.log", "a") as log:
        if not shutil.which("docker", path=env.get("PATH")):
            log.write("docker: command not found on this server\n")
            return list(images)
        for img in images:
            r = subprocess.run(["docker", "image", "inspect", img], env=env, capture_output=True, text=True)
            if r.returncode == 0:
                log.write(f"{img}: already in Docker; not pulled\n")
                continue
            r = subprocess.run(["docker", "pull", img], env=env, capture_output=True, text=True)
            log.write(f"pull {img}: exit {r.returncode}\n{r.stdout[-2000:]}{r.stderr[-2000:]}\n")
            if r.returncode != 0:
                # a registry Docker cannot reach fails every pull after a timeout: stop at the first one
                failed.append(img)
                log.write("stopped at the first image that could not be pulled\n")
                break
    return failed


def _blobs_match(udocker_dir: Path, img: str) -> bool:
    import hashlib
    name, _, tag = img.rpartition(":")
    tagdir = udocker_dir / "repos" / name / tag
    blobs = sorted(tagdir.glob("sha256:*")) if tagdir.is_dir() else []
    if not blobs:
        return False
    for b in blobs:
        h = hashlib.sha256()
        with open(b.resolve(), "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if "sha256:" + h.hexdigest() != b.name:
            return False
    return True
