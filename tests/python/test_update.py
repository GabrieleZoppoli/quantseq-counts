import json

from quantseq_counts import __version__, cli, update


def fetch_of(tag):
    return lambda url, timeout: json.dumps({"tag_name": tag}).encode()


def offline(url, timeout):
    raise OSError("no network")


def test_latest_release():
    assert update.latest_release(fetch=fetch_of("v9.1.0")) == "9.1.0"
    assert update.latest_release(fetch=offline) is None
    assert update.latest_release(fetch=lambda u, t: b"not json") is None


def test_newer():
    assert update.is_newer("0.10.0", "0.9.9") and not update.is_newer("0.1.0", "0.1.0") and not update.is_newer("0.0.9", "0.1.0")


def test_notice():
    assert "9.1.0" in update.notice(fetch=fetch_of("v9.1.0")) and "quantseq-counts update" in update.notice(fetch=fetch_of("v9.1.0"))
    assert update.notice(fetch=fetch_of("v" + __version__)) is None
    assert update.notice(fetch=offline) is None


def test_update_installs_beside_and_switches(tmp_path):
    calls = []
    rc = update.install_version("9.1.0", tmp_path, installer=lambda v, dest: calls.append((v, dest)) or 0)
    assert rc == 0 and calls == [("9.1.0", tmp_path / "versions" / "9.1.0")]
    assert (tmp_path / "CURRENT").read_text() == "9.1.0\n"


def test_update_failure_does_not_switch(tmp_path):
    (tmp_path / "CURRENT").write_text("0.1.0\n")
    assert update.install_version("9.1.0", tmp_path, installer=lambda v, d: 1) == 1
    assert (tmp_path / "CURRENT").read_text() == "0.1.0\n"


def test_cli_update_up_to_date(monkeypatch, capsys):
    monkeypatch.setattr(update, "latest_release", lambda **k: __version__)
    assert cli.main(["update"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_update_installs_under_the_root(monkeypatch, tmp_path, capsys):
    root = tmp_path / "root"
    monkeypatch.setenv("QUANTSEQ_COUNTS_ROOT", str(root))
    monkeypatch.setattr(update, "latest_release", lambda **k: "9.9.9")
    seen = []
    monkeypatch.setattr(update, "install_version", lambda v, prefix: seen.append((v, prefix)) or 0)
    assert cli.main(["update"]) == 0 and seen == [("9.9.9", root)]
