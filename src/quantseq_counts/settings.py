"""The settings of a run: the schema, defaults, validation, changes from the standard and warnings."""

import json
import re
from pathlib import Path

import yaml

from . import __version__

_SCHEMA_FILE = Path(__file__).resolve().parents[2] / "schema" / "settings.schema.json"
SCHEMA: dict = json.loads(_SCHEMA_FILE.read_text())["settings"]


def load_settings(path: Path) -> dict:
    data = yaml.safe_load(Path(path).read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected key: value lines")
    return data


def with_defaults(s: dict) -> dict:
    out = {k: e["default"] for k, e in SCHEMA.items()}
    out.update(s)
    return out


def _type_ok(typ: str, v) -> bool:
    if typ in ("string", "path"):
        return isinstance(v, str)
    if typ == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if typ == "integer_or_null":
        return v is None or (isinstance(v, int) and not isinstance(v, bool))
    if typ == "boolean":
        return isinstance(v, bool)
    raise ValueError(f"unknown type {typ}")


def validate(s: dict, accept_version_change: bool = False) -> list[str]:
    errs = [f"{k}: not a setting of quantseq-counts" for k in s if k not in SCHEMA]
    full = with_defaults({k: v for k, v in s.items() if k in SCHEMA})
    for k, e in SCHEMA.items():
        v = full[k]
        needed = e.get("required") or any(full.get(a) == b for a, b in e.get("required_if", {}).items())
        if v is None or v == "":
            if needed:
                errs.append(f"{k}: required ({e['help']})")
            continue
        if not _type_ok(e["type"], v):
            errs.append(f"{k}: expected {e['type'].replace('_or_null', '')}, got {v!r}")
            continue
        if "enum" in e and v not in e["enum"]:
            errs.append(f"{k}: {v!r} is not one of {', '.join(map(str, e['enum']))}")
        if "pattern" in e and not re.search(e["pattern"], v):
            errs.append(f"{k}: {v!r} does not match {e['pattern']}")
        if "minimum" in e and v < e["minimum"]:
            errs.append(f"{k}: must be at least {e['minimum']}")
    pv = full.get("package_version")
    if pv and pv != __version__ and not accept_version_change:
        errs.append(f"package_version: these settings were written by quantseq-counts {pv}, this is {__version__}; "
                    "counts can differ between versions. Use the version that started the study, or rerun with "
                    "--accept-version-change")
    return errs


def changes_from_default(s: dict) -> list[tuple]:
    # paths, names and the version are the run's own facts, not changes from the standard
    own = lambda e: e.get("required") or e.get("required_if") or e["type"] == "path"
    return [(k, e["default"], s[k]) for k, e in SCHEMA.items()
            if k in s and not own(e) and s[k] != e["default"]]


def warnings_for(s: dict) -> list[str]:
    full = with_defaults(s)
    return [e["warning"] for k, e in SCHEMA.items() if "warn_if" in e and full[k] in e["warn_if"]]
