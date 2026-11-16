import gzip
import os
import json
import sys
from pathlib import Path

import pytest
import yaml

from quantseq_counts import __version__, cli
from quantseq_counts import settings as st

FIX = Path(__file__).parent / "fixtures"


def fastq(path, seq="AAAAAATATAGGGGCCCC", n=20):
    with gzip.open(path, "wt") as f:
        f.write("".join(f"@r{i}\n{seq}\n+\n{'I' * len(seq)}\n" for i in range(n)))


@pytest.fixture
def study(tmp_path):
    fq = tmp_path / "fq"; fq.mkdir()
    fastq(fq / "a.fastq.gz"); fastq(fq / "b.fastq.gz")
    (tmp_path / "samples.csv").write_text("sample,fastq\nA,a.fastq.gz\nB,b.fastq.gz\n")
    s = {"package_version": __version__, "run_name": "t1", "fastq_dir": str(fq),
         "samples": str(tmp_path / "samples.csv"), "outdir": str(tmp_path / "out"),
         "reference_dir": str(tmp_path / "ref"), "engine": "udocker"}
    (tmp_path / "settings.yaml").write_text(yaml.safe_dump(s))
    return tmp_path


@pytest.fixture(autouse=True)
def no_image_pulls(monkeypatch):
    monkeypatch.setattr(cli.launch, "load_pins", lambda install: {})
    monkeypatch.setattr(cli.update, "notice", lambda: None)
    monkeypatch.setattr(cli.launch, "inspect_processes", lambda s, rd, inst, env: [("P", "x/y:1")])
    monkeypatch.setattr(cli.launch, "udocker_pull", lambda images, env, rd, pins=None: [])
    monkeypatch.setattr(cli.launch, "docker_pull", lambda images, env, rd: [])


def run(study, *extra):
    return cli.main(["run", "--settings", str(study / "settings.yaml"), "--samples", str(study / "samples.csv"),
                     "--install", str(study / "install"), "--yes", *extra])


def test_version(capsys):
    assert cli.main(["--version"]) == 0
    assert __version__ in capsys.readouterr().out


def test_run_stops_on_mismatch(study, capsys):
    (study / "samples.csv").write_text("sample,fastq\nA,a.fastq.gz\nC,c.fastq.gz\n")
    assert run(study, "--dry-run") == 2
    assert "c.fastq.gz" in capsys.readouterr().err
    assert not (study / "out").exists()


def test_run_stops_on_invalid_settings(study, capsys):
    s = yaml.safe_load((study / "settings.yaml").read_text()); s["library"] = "rev"
    (study / "settings.yaml").write_text(yaml.safe_dump(s))
    assert run(study, "--dry-run") == 2
    assert "library" in capsys.readouterr().err


def test_refuses_finished_outdir(study, capsys):
    rd = study / "out" / "run"; rd.mkdir(parents=True)
    (rd / "DONE").write_text("finished")
    assert run(study, "--dry-run") == 3
    assert run(study, "--dry-run", "--resume") == 3
    (rd / "DONE").unlink()
    assert run(study, "--dry-run") == 3          # an unfinished run is there: --resume or another outdir
    assert run(study, "--dry-run", "--resume") == 0


def test_counts_without_done_can_resume(study):
    rd = study / "out" / "run"; rd.mkdir(parents=True)
    (study / "out" / "counts.tsv").write_text("x")  # published before QC failed
    assert run(study, "--dry-run", "--resume") == 0


def test_dry_run_command(study, capsys):
    assert run(study, "--dry-run") == 0
    out = capsys.readouterr().out
    argv = json.loads(out.strip().splitlines()[-1])
    assert argv[1] == "run" and argv[2].endswith("workflow/main.nf")
    assert "-params-file" in argv and "-c" in argv
    assert argv[argv.index("-profile") + 1] == "udocker"
    assert argv[argv.index("-w") + 1] == str(study / "out" / "work")
    assert "-resume" not in argv
    assert not (study / "out").exists()


def test_umi_disagreement_warned(study, capsys):
    fastq(study / "fq" / "a.fastq.gz", seq="AAAAAACCCCGGGGCCCC")
    fastq(study / "fq" / "b.fastq.gz", seq="AAAAAACCCCGGGGCCCC")
    assert run(study, "--dry-run") == 0
    assert "UMI spacer" in capsys.readouterr().err


def test_run_writes_run_files(study, monkeypatch):
    calls = []
    monkeypatch.setattr(cli.launch, "start", lambda argv, env, run_dir: calls.append((argv, run_dir)) or 4242)
    assert run(study) == 0
    rd = study / "out" / "run"
    written = yaml.safe_load((rd / "settings.yaml").read_text())
    assert written["library"] == "fwd_umi" and written["samples"] == str(rd / "samples.csv")
    assert (rd / "samples.csv").read_text() == "sample,fastq,group\nA,a.fastq.gz,\nB,b.fastq.gz,\n"
    assert (rd / "changes.tsv").read_text() == "setting\tstandard\tthis_run\nengine\tapptainer\tudocker\n"
    assert calls and calls[0][1] == rd


def test_setup_writes_same_files_as_form(tmp_path, monkeypatch):
    fq = tmp_path / "fq"; fq.mkdir(); fastq(fq / "L1_S1.fastq.gz"); fastq(fq / "L2_S2.fastq.gz")
    answers = json.loads((FIX / "form_answers.json").read_text())
    answers["fastq_dir"] = str(fq)
    script = iter([answers["run_name"], answers["fastq_dir"], "", answers["library"], answers["reference"],
                   answers["reference_dir"], answers["outdir"], answers["engine"], answers["executor"],
                   str(answers["max_cpus"]), answers["max_memory"], "n"])
    monkeypatch.chdir(tmp_path)
    assert cli.main(["setup"], ask=lambda prompt: next(script)) == 0
    expected = (FIX / "form_settings.yaml").read_text().replace("@FASTQ_DIR@", str(fq)).replace(
        "@SAMPLES@", str(tmp_path / "samples.csv"))
    assert (tmp_path / "settings.yaml").read_text() == expected
    assert (tmp_path / "samples.csv").read_text() == "sample,fastq,group\nL1_S1,L1_S1.fastq.gz,\nL2_S2,L2_S2.fastq.gz,\n"


def test_setup_reasks_invalid_answer(tmp_path, monkeypatch, capsys):
    fq = tmp_path / "fq"; fq.mkdir(); fastq(fq / "a.fastq.gz")
    script = iter(["bad name", "ok1", str(tmp_path / "nowhere"), str(fq), "", "", "", str(tmp_path / "ref"),
                   str(tmp_path / "out"), "", "", "", "", "n"])
    monkeypatch.chdir(tmp_path)
    assert cli.main(["setup"], ask=lambda prompt: next(script)) == 0
    err = capsys.readouterr().err
    assert "run_name" in err and "nowhere" in err
    s = st.load_settings(tmp_path / "settings.yaml")
    assert s["run_name"] == "ok1" and s["library"] == "fwd_umi" and s["engine"] == "apptainer"


def test_foreground_returns_nextflow_status(study, monkeypatch):
    monkeypatch.setattr(cli.launch, "run_foreground", lambda argv, env, run_dir: 7)
    assert run(study, "--foreground") == 7
    assert (study / "out" / "run" / "settings.yaml").exists()


def test_run_foreground_logs(tmp_path):
    rc = cli.launch.run_foreground(["sh", "-c", "echo hello; exit 3"], dict(os.environ), tmp_path)
    assert rc == 3 and "hello" in (tmp_path / "nextflow.log").read_text()


def test_failed_pull_stops(study, monkeypatch, capsys):
    monkeypatch.setattr(cli.launch, "udocker_pull", lambda images, env, rd, pins=None: ["x/y:1"])
    monkeypatch.setattr(cli.launch, "start", lambda *a: pytest.fail("must not start"))
    assert run(study) == 2
    assert "x/y:1" in capsys.readouterr().err


def test_extra_config_appended(study, capsys, tmp_path):
    extra = tmp_path / "threads.config"; extra.write_text("process.cpus = 3\n")
    assert run(study, "--dry-run", "--extra-config", str(extra)) == 0
    argv = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    i = [k for k, a in enumerate(argv) if a == "-c"]
    assert len(i) == 2 and argv[i[1] + 1] == str(extra) and i[1] > i[0]


def test_paths_absolute_from_the_settings_folder(study, monkeypatch):
    monkeypatch.setattr(cli.launch, "start", lambda argv, env, run_dir: 1)
    monkeypatch.setenv("HOME", str(study / "home"))
    s = yaml.safe_load((study / "settings.yaml").read_text())
    s.update({"reference_dir": "refs", "fastq_dir": "fq", "outdir": "~/out2"})
    (study / "settings.yaml").write_text(yaml.safe_dump(s))
    monkeypatch.chdir(study.parent)               # the shell is elsewhere: paths follow the settings file
    assert run(study) == 0
    w = yaml.safe_load((study / "home" / "out2" / "run" / "settings.yaml").read_text())
    assert w["reference_dir"] == str(study / "refs") and w["fastq_dir"] == str(study / "fq")
    assert w["outdir"] == str(study / "home" / "out2")


def test_missing_custom_reference_stops(study, capsys):
    s = yaml.safe_load((study / "settings.yaml").read_text())
    s.update({"reference": "custom", "fasta": str(study / "nope.fa.gz"), "gtf": str(study / "nope.gtf.gz")})
    (study / "settings.yaml").write_text(yaml.safe_dump(s))
    assert run(study, "--dry-run") == 2
    err = capsys.readouterr().err
    assert "nope.fa.gz" in err and "nope.gtf.gz" in err


def test_setup_keeps_existing_files_unless_told(tmp_path, monkeypatch, capsys):
    # settings.yaml or samples.csv already in the folder: setup asks first, and "n" (the default) leaves them alone
    (tmp_path / "samples.csv").write_text("sample,fastq\nmine,mine.fastq.gz\n")
    monkeypatch.chdir(tmp_path)
    prompts = []
    rc = cli.main(["setup"], ask=lambda prompt: prompts.append(prompt) or "")
    assert rc == cli.REFUSED and len(prompts) == 1 and "samples.csv" in prompts[0]
    assert (tmp_path / "samples.csv").read_text() == "sample,fastq\nmine,mine.fastq.gz\n"
    assert not (tmp_path / "settings.yaml").exists()


def test_run_with_damaged_fastq_stops_with_a_message(study, capsys):
    p = study / "fq" / "a.fastq.gz"
    p.write_bytes(p.read_bytes()[:30])
    assert run(study) == cli.CHECK_FAILED
    assert "a.fastq.gz" in capsys.readouterr().err


def test_run_stops_when_inspect_fails(study, monkeypatch, capsys):
    def boom(s, rd, inst, env):
        raise RuntimeError("nextflow inspect failed: see /x/run/inspect.log")
    monkeypatch.setattr(cli.launch, "inspect_processes", boom)
    assert run(study) == cli.CHECK_FAILED
    assert "inspect.log" in capsys.readouterr().err


def test_outdir_link_target_is_mounted(study, monkeypatch):
    # outdir is a symbolic link to a folder elsewhere: the containers must see the link's target
    monkeypatch.setattr(cli.launch, "run_foreground", lambda argv, env, run_dir: 0)
    target = study.parent / (study.name + "_elsewhere") / "results"; target.mkdir(parents=True)
    (study / "out").symlink_to(target)
    assert run(study, "--foreground") == 0
    assert str(target.resolve()) in (target / "run" / "run.config").read_text()


def test_setup_slurm_asks_the_job_limits(tmp_path, monkeypatch):
    # with SLURM, max_cpus, max_memory and max_time are the most one job may ask for: setup asks all three
    fq = tmp_path / "fq"; fq.mkdir(); fastq(fq / "a.fastq.gz")
    prompts = []
    script = iter(["s1", str(fq), "", "", "", str(tmp_path / "ref"), str(tmp_path / "out"), "", "slurm",
                   "short", "", "8", "64 GB", "12 h", "n"])
    monkeypatch.chdir(tmp_path)
    assert cli.main(["setup"], ask=lambda prompt: prompts.append(prompt) or next(script)) == 0
    s = st.load_settings(tmp_path / "settings.yaml")
    assert s["slurm_queue"] == "short" and s["max_cpus"] == 8 and s["max_memory"] == "64 GB" and s["max_time"] == "12 h"


def test_docker_failed_pull_stops_with_a_plain_reason(study, monkeypatch, capsys):
    s = yaml.safe_load((study / "settings.yaml").read_text()); s["engine"] = "docker"
    (study / "settings.yaml").write_text(yaml.safe_dump(s))
    monkeypatch.setattr(cli.launch, "docker_pull", lambda images, env, rd: ["x/y:1"])
    monkeypatch.setattr(cli.launch, "start", lambda *a: pytest.fail("must not start"))
    assert run(study) == 2
    err = capsys.readouterr().err
    assert "x/y:1" in err and "proxy" in err and "udocker" in err


def test_docker_with_slurm_does_not_pull_on_this_machine(study, monkeypatch):
    s = yaml.safe_load((study / "settings.yaml").read_text())
    s.update(engine="docker", executor="slurm", slurm_queue="q")
    (study / "settings.yaml").write_text(yaml.safe_dump(s))
    monkeypatch.setattr(cli.launch, "docker_pull", lambda *a: pytest.fail("the nodes pull, not this machine"))
    monkeypatch.setattr(cli.launch, "start", lambda *a: 1)
    assert run(study) == 0


def test_image_check_line_is_shown_before_the_pull_starts(study, monkeypatch):
    # when the output goes to a pipe or a file, the line must not wait behind the pull and its error messages
    events = []

    class Out:
        def write(self, t):
            if t.strip():
                events.append("write")
        def flush(self):
            events.append("flush")

    s = yaml.safe_load((study / "settings.yaml").read_text()); s["engine"] = "docker"
    (study / "settings.yaml").write_text(yaml.safe_dump(s))
    monkeypatch.setattr(cli.launch, "docker_pull", lambda images, env, rd: events.append("pull") or [])
    monkeypatch.setattr(cli.launch, "start", lambda *a: 1)
    monkeypatch.setattr(sys, "stdout", Out())
    run(study)
    i = events.index("pull")
    assert "flush" in events[:i] and events[:i].index("flush") > events[:i].index("write")
