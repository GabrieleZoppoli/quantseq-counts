"""`quantseq-counts bug-report RUN_OUTDIR`: a small bundle for a public GitHub issue, with sample names replaced by
S01, S02, ... (in sample-list order), the run name by <run>, every absolute path by <path>, the host name by
<host> and the user name by <user>. It keeps the versions, the settings, the failing step and its last log lines.
Read it before posting it."""

import csv
import getpass
import io
import re
import socket
import tarfile
import time
from pathlib import Path

PATH = re.compile(r"(?<![\w.])/(?:[^\s'\"`:;,()\[\]{}<>]+)")


def _scrubber(run_dir: Path):
    names = []
    sfile = run_dir / "samples.csv"
    if sfile.exists():
        names = [r["sample"] for r in csv.DictReader(io.StringIO(sfile.read_text(encoding="utf-8-sig")))]
    subs = sorted(((n, f"S{i:02d}") for i, n in enumerate(names, 1)), key=lambda x: -len(x[0]))
    settings = (run_dir / "settings.yaml").read_text() if (run_dir / "settings.yaml").exists() else ""
    m = re.search(r"^run_name:\s*'?([^'\n]+)'?", settings, re.M)
    run_name = m.group(1).strip() if m else None
    hosts = {h for h in (socket.gethostname(), socket.getfqdn()) if h}
    user = getpass.getuser()

    def scrub(text: str) -> str:
        text = PATH.sub("<path>", text)
        for n, s in subs:
            text = re.sub(rf"(?<![A-Za-z0-9]){re.escape(n)}(?![A-Za-z0-9])", s, text)
        if run_name:
            text = text.replace(run_name, "<run>")
        for h in sorted(hosts, key=len, reverse=True):
            text = text.replace(h, "<host>")
        if user and len(user) > 2:
            text = re.sub(rf"\b{re.escape(user)}\b", "<user>", text)
        return text
    return scrub


def _tail(p: Path, n: int = 50) -> str:
    return "\n".join(p.read_text(errors="replace").splitlines()[-n:]) + "\n" if p.exists() else ""


def make_bundle(outdir: Path, dest_dir: Path) -> Path:
    run_dir = Path(outdir) / "run"
    scrub = _scrubber(run_dir)
    parts = {}
    for f in ("settings.yaml", "versions.tsv", "containers.tsv", "changes.tsv"):
        if (run_dir / f).exists():
            parts[f] = (run_dir / f).read_text()
    parts["nextflow.log.tail"] = _tail(run_dir / "nextflow.log", 80)
    trace = run_dir / "trace.txt"
    if trace.exists():
        rows = list(csv.DictReader(io.StringIO(trace.read_text()), delimiter="\t"))
        failed = [r for r in rows if r.get("status") == "FAILED"]
        lines = ["process\texit\tcontainer"]
        for i, r in enumerate(failed, 1):
            lines.append(f"{r['name']}\t{r['exit']}\t{r['container']}")
            w = Path(r.get("workdir", ""))
            parts[f"failed_{i}.command.sh"] = _tail(w / ".command.sh", 60)
            parts[f"failed_{i}.command.err"] = _tail(w / ".command.err", 50)
            parts[f"failed_{i}.command.log"] = _tail(w / ".command.log", 50)
        parts["failed_steps.tsv"] = "\n".join(lines) + "\n"
    dest_dir = Path(dest_dir); dest_dir.mkdir(parents=True, exist_ok=True)
    bundle = dest_dir / f"bug-report-{time.strftime('%Y%m%d-%H%M%S')}.tar.gz"
    with tarfile.open(bundle, "w:gz") as tf:
        for name, text in parts.items():
            data = scrub(text).encode()
            info = tarfile.TarInfo(f"bug-report/{name}"); info.size = len(data); info.mtime = int(time.time())
            tf.addfile(info, io.BytesIO(data))
    return bundle
