#!/usr/bin/env python3
"""Prints docs/settings.md, the list of every setting with its default and explanation, from the schema.
Usage: python3 tools/settings_doc.py > docs/settings.md"""
import json
from pathlib import Path

schema = json.loads((Path(__file__).resolve().parents[1] / "schema" / "settings.schema.json").read_text())


def show(v):
    return "(empty)" if v is None else f"`{str(v).lower() if isinstance(v, bool) else v}`"


lines = ["# Settings", "",
         "Every setting can be changed in the form, in `quantseq-counts setup` or in `settings.yaml`. The default is the "
         "standard; a run lists every change from it on the first page of its quality report.", ""]
for group, title in (("basic", "Basic settings"), ("advanced", "Advanced settings")):
    lines += [f"## {title}", "", "| Setting | Default | What it does |", "|---|---|---|"]
    for k, e in schema["settings"].items():
        if e["group"] != group:
            continue
        what = e["help"]
        if "enum" in e:
            what += " Values: " + ", ".join(f"`{x}`" for x in e["enum"]) + "."
        if "warning" in e:
            what += f" **Warning shown when changed:** {e['warning']}"
        lines.append(f"| `{k}` | {show(e['default'])} | {what} |")
    lines.append("")
print("\n".join(lines), end="")
