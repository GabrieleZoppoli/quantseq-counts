import subprocess
import sys
from pathlib import Path

from quantseq_counts import settings as st

ROOT = Path(__file__).resolve().parents[2]


def test_every_setting_documented_and_page_current():
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "settings_doc.py")], capture_output=True, text=True, check=True).stdout
    for k, e in st.SCHEMA.items():
        assert f"`{k}`" in out and e["help"] in out, k
        if "warning" in e:
            assert e["warning"] in out, k
    assert (ROOT / "docs" / "settings.md").read_text() == out, "docs/settings.md is out of date: run tools/settings_doc.py > docs/settings.md"
