"""Release notice at each run, and `quantseq-counts update`: a newer version is installed beside the current one
and used only when the helper asks for it; every installed version stays runnable (--use VERSION)."""

import json
import re
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from . import __version__

REPO = "GabrieleZoppoli/quantseq-counts"
API = f"https://api.github.com/repos/{REPO}/releases/latest"


def _get(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": "quantseq-counts", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def latest_release(timeout: float = 3, fetch=_get) -> str | None:
    try:
        tag = json.loads(fetch(API, timeout))["tag_name"]
    except Exception:
        return None
    return tag[1:] if tag.startswith("v") else tag


def _key(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v))


def is_newer(candidate: str, current: str) -> bool:
    return _key(candidate) > _key(current)


def notice(fetch=_get) -> str | None:
    latest = latest_release(fetch=fetch)
    if latest and is_newer(latest, __version__):
        return (f"quantseq-counts {latest} is available (this is {__version__}). Nothing changes unless you type "
                "`quantseq-counts update`; a study can stay on the version it started with.")
    return None


def _install_from_github(version: str, dest: Path) -> int:
    url = f"https://github.com/{REPO}/archive/refs/tags/v{version}.tar.gz"
    with tempfile.TemporaryDirectory() as t:
        tgz = Path(t) / "src.tar.gz"
        tgz.write_bytes(_get(url, 120))
        with tarfile.open(tgz) as tf:
            tf.extractall(t, filter="data")
        src = next(p for p in Path(t).iterdir() if p.is_dir())
        return subprocess.call(["bash", str(src / "install.sh"), "--prefix", str(dest)])


def install_version(version: str, prefix: Path, installer=_install_from_github) -> int:
    dest = Path(prefix) / "versions" / version
    rc = installer(version, dest)
    if rc == 0:
        (Path(prefix) / "CURRENT").write_text(version + "\n")
    return rc
