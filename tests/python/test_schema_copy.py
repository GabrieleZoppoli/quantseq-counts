import json
from pathlib import Path

from quantseq_counts import __version__

ROOT = Path(__file__).resolve().parents[2]


def test_form_schema_is_the_same_file():
    assert (ROOT / "docs" / "settings.schema.json").read_bytes() == (ROOT / "schema" / "settings.schema.json").read_bytes()


def test_schema_names_the_package_version():
    assert json.loads((ROOT / "schema" / "settings.schema.json").read_text())["package_version"] == __version__
