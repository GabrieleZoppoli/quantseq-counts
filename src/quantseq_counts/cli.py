"""The quantseq-counts command: setup, run and the others."""

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__, bugreport, launch, selftest, update
from . import samples as sm
from . import settings as st

OK, CHECK_FAILED, REFUSED = 0, 2, 3


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def default_install() -> Path:
    return Path(os.environ.get("QUANTSEQ_COUNTS_HOME", Path(__file__).resolve().parents[2]))


def default_root() -> Path:
    """The first installation, under which `update` puts every later version (versions/<version>)."""
    return Path(os.environ.get("QUANTSEQ_COUNTS_ROOT", default_install()))


# ---------------------------------------------------------------- setup

def _question(ask, key, check=None, default=None, label=None):
    e = st.SCHEMA[key]
    d = e["default"] if default is None else default
    shown = "" if d is None else f" [{d}]"
    while True:
        raw = ask(f"{label or e['help']}{shown}\n{key}: ").strip()
        v = d if raw == "" else raw
        if e["type"] in ("integer", "integer_or_null") and isinstance(v, str):
            try:
                v = int(v)
            except ValueError:
                pass
        if e["type"] in ("boolean", "auto_or_boolean") and isinstance(v, str):
            v = {"true": True, "yes": True, "y": True, "false": False, "no": False, "n": False}.get(v.lower(), v)
        probe = {"package_version": __version__, key: v}
        errs = [x for x in st.validate(probe) if x.startswith(key + ":")]
        if check and not errs:
            errs = check(v)
        if not errs:
            return v
        for x in errs:
            _err(x)


def _exists_dir(v):
    return [] if Path(v).is_dir() else [f"fastq_dir: {v} is not a folder on this server"]


def _samples_from_names(fastq_dir: Path) -> str:
    rows = ["sample,fastq,group"]
    for p in sorted(fastq_dir.iterdir()):
        for suf in sm.FASTQ_SUFFIXES:
            if p.name.endswith(suf):
                rows.append(f"{p.name[: -len(suf)]},{p.name},")
                break
    return "\n".join(rows) + "\n"


def cmd_setup(args, ask) -> int:
    there = [f for f in ("settings.yaml", "samples.csv") if Path(f).exists()]
    if there and ask(f"{' and '.join(there)} already in this folder; replace? [n]\n").strip().lower() not in ("y", "yes"):
        _err(f"nothing written: {' and '.join(there)} kept (run setup in another folder, or answer y)")
        return REFUSED
    s = {"package_version": __version__}
    s["run_name"] = _question(ask, "run_name")
    s["fastq_dir"] = _question(ask, "fastq_dir", check=_exists_dir)
    fq = Path(s["fastq_dir"])
    while True:
        raw = ask("Sample list (samples.csv) to use, or press Enter to build it from the FASTQ file names\nsamples: ").strip()
        try:
            if raw == "":
                Path("samples.csv").write_text(_samples_from_names(fq))
            else:
                Path("samples.csv").write_bytes(Path(raw).read_bytes())
            rows = sm.read_samples(Path("samples.csv"))
            errors, warnings = sm.check_folder(rows, fq)
        except (OSError, ValueError) as e:
            _err(str(e)); continue
        for w in warnings:
            _err("warning: " + w)
        if errors:
            for x in errors:
                _err(x)
            continue
        break
    s["samples"] = "samples.csv"
    s["library"] = _question(ask, "library")
    try:
        share = sm.probe_umi(fq / rows[0].fastq)
    except ValueError as e:
        _err(str(e)); return CHECK_FAILED
    msg = sm.umi_disagreement(s["library"], share)
    if msg:
        _err("warning: " + msg)
    s["reference"] = _question(ask, "reference")
    if s["reference"] == "custom":
        s["fasta"] = _question(ask, "fasta")
        s["gtf"] = _question(ask, "gtf")
    s["reference_dir"] = _question(ask, "reference_dir")
    s["outdir"] = _question(ask, "outdir")
    s["engine"] = _question(ask, "engine")
    s["executor"] = _question(ask, "executor")
    if s["executor"] == "local":
        s["max_cpus"] = _question(ask, "max_cpus")
        s["max_memory"] = _question(ask, "max_memory")
    else:
        s["slurm_queue"] = _question(ask, "slurm_queue")
        s["slurm_account"] = _question(ask, "slurm_account", default="")  or None
    if ask("Change advanced settings? [n]\n").strip().lower() in ("y", "yes"):
        for k, e in st.SCHEMA.items():
            if e["group"] == "advanced":
                s[k] = _question(ask, k)
    for w in st.warnings_for(s):
        _err("warning: " + w)
    errs = st.validate(s)
    if errs:
        for x in errs:
            _err(x)
        return CHECK_FAILED
    Path("settings.yaml").write_text(st.dump_settings(s))
    print("Wrote settings.yaml and samples.csv. Start the run with:\n"
          "  quantseq-counts run --settings settings.yaml --samples samples.csv")
    return OK


# ---------------------------------------------------------------- run

def cmd_run(args, ask) -> int:
    sfile = Path(args.settings)
    try:
        s = st.load_settings(sfile)
    except (OSError, ValueError) as e:
        _err(str(e)); return CHECK_FAILED
    errs = st.validate(s, accept_version_change=args.accept_version_change)
    if errs:
        for x in errs:
            _err(x)
        return CHECK_FAILED
    s = st.with_defaults(s)
    # every path setting: ~ expanded, and a relative path taken from the folder of the settings file
    base = sfile.absolute().parent
    for k, e in st.SCHEMA.items():
        if e["type"] == "path" and s.get(k):
            p = Path(os.path.expanduser(str(s[k])))
            s[k] = str(p if p.is_absolute() else base / p)
    if s["reference"] == "custom":
        missing = [k for k in ("fasta", "gtf") if not Path(s[k]).is_file()]
        if missing:
            for k in missing:
                _err(f"{k}: {s[k]} not found")
            return CHECK_FAILED
    samples_file = Path(args.samples) if args.samples else Path(s["samples"])
    try:
        rows = sm.read_samples(samples_file)
    except (OSError, ValueError) as e:
        _err(str(e)); return CHECK_FAILED
    fq = Path(s["fastq_dir"])
    errors, warnings = sm.check_folder(rows, fq)
    if errors:
        for x in errors:
            _err(x)
        return CHECK_FAILED
    for r in rows:
        try:
            msg = sm.umi_disagreement(s["library"], sm.probe_umi(fq / r.fastq))
        except ValueError as e:
            _err(str(e)); return CHECK_FAILED
        if msg:
            warnings.append(f"{r.name}: {msg}")
    warnings += st.warnings_for(s)
    out = Path(s["outdir"]).absolute()
    if (out / "run" / "DONE").exists():
        _err(f"{out} holds a finished run (run/DONE): choose another outdir"); return REFUSED
    if (out / "run").exists() and not args.resume:
        _err(f"{out} holds an unfinished run: add --resume to continue it, or choose another outdir"); return REFUSED
    for w in warnings:
        _err("warning: " + w)
    if warnings and not args.yes and not args.dry_run:
        if ask("Start anyway? [y/N] ").strip().lower() not in ("y", "yes"):
            return CHECK_FAILED
    s["outdir"] = str(out)
    s["fastq_dir"] = str(fq.absolute())
    install = Path(args.install) if args.install else default_install()
    run_dir = out / "run"
    paths = [fq] + [fq / r.fastq for r in rows] + [Path(s["reference_dir"]), out.parent] + ([out] if out.exists() else [])
    if s["reference"] == "custom":
        paths += [Path(s["fasta"]), Path(s["gtf"])]
    mounts = launch.container_mounts(paths)
    argv = launch.nextflow_command(s, run_dir, install, resume=args.resume)
    if args.extra_config:
        i = argv.index("-params-file")
        argv[i:i] = ["-c", str(Path(args.extra_config).absolute())]
    if args.dry_run:
        print(json.dumps(argv))
        return OK
    launch.write_run_files(s, samples_file, run_dir, mounts)
    env = launch.engine_env(s, run_dir, install)
    try:
        procs = launch.inspect_processes(s, run_dir, install, env)
    except RuntimeError as e:
        _err(str(e)); return CHECK_FAILED
    pins = launch.load_pins(install)
    launch.write_containers(procs, run_dir, pins)
    if s["engine"] == "udocker":
        print("Checking the container images (pulled only when absent; the first time this can take a while)")
        failed = launch.udocker_pull(sorted({c for _p, c in procs if c}), env, run_dir, pins)
        if failed:
            _err("These images could not be pulled or checked (see " + str(run_dir / "images.log") + "):")
            for f in failed:
                _err("  " + f)
            return CHECK_FAILED
    if args.foreground:
        rc = launch.run_foreground(argv, env, run_dir)
        print(f"Nextflow ended with exit status {rc} (log: {run_dir / 'nextflow.log'})")
        return rc
    pid = launch.start(argv, env, run_dir)
    print(f"Started (process {pid}). Follow it with:\n  tail -f {run_dir / 'nextflow.log'}")
    return OK


def cmd_update(args) -> int:
    latest = args.version or update.latest_release()
    if latest is None:
        _err("Could not reach GitHub to find the latest release; give one with --version")
        return CHECK_FAILED
    if not args.version and not update.is_newer(latest, __version__):
        print(f"quantseq-counts {__version__} is up to date")
        return OK
    prefix = default_root()
    print(f"Installing quantseq-counts {latest} in {prefix / 'versions' / latest}; {__version__} stays installed")
    rc = update.install_version(latest, prefix)
    if rc == OK:
        print(f"From now on quantseq-counts runs {latest}. To run {__version__} again: quantseq-counts --use {__version__} ...")
    return rc


def cmd_bug_report(args) -> int:
    b = bugreport.make_bundle(Path(args.outdir), Path.cwd())
    print(f"Wrote {b}. Open it and read it before attaching it to a GitHub issue: sample names, paths and host names "
          "are replaced, but check that nothing about your study is left.")
    return OK


def main(argv=None, ask=input) -> int:
    p = argparse.ArgumentParser(prog="quantseq-counts")
    p.add_argument("--version", action="store_true")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("setup", help="answer questions; writes settings.yaml and samples.csv")
    r = sub.add_parser("run", help="check the settings and samples, then start the run")
    r.add_argument("--settings", required=True)
    r.add_argument("--samples")
    r.add_argument("--resume", action="store_true")
    r.add_argument("--accept-version-change", action="store_true")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--yes", action="store_true", help="do not ask before starting when there are warnings")
    r.add_argument("--foreground", action="store_true", help="wait for the run to end (for job scripts)")
    r.add_argument("--install", help=argparse.SUPPRESS)
    r.add_argument("--extra-config", help=argparse.SUPPRESS)  # release checks only (other thread counts)
    te = sub.add_parser("test", help="run the bundled public data and compare the counts with the stored ones")
    te.add_argument("--engine", default="apptainer", choices=["apptainer", "udocker", "docker"])
    te.add_argument("--workdir", default="quantseq-counts-test")
    te.add_argument("--library", default="both", choices=["both", "fwd_umi", "fwd_no_umi"])
    te.add_argument("--max-cpus", type=int, default=4)
    te.add_argument("--max-memory", default="14 GB")
    te.add_argument("--write-expected", action="store_true", help=argparse.SUPPRESS)
    u = sub.add_parser("update", help="install a newer release beside this one (only when you type it)")
    u.add_argument("--version")
    br = sub.add_parser("bug-report", help="a scrubbed bundle of a failed run, for a GitHub issue")
    br.add_argument("outdir")
    a = p.parse_args(argv)
    if a.version:
        print(f"quantseq-counts {__version__}")
        return OK
    if a.cmd == "setup":
        return cmd_setup(a, ask)
    if a.cmd == "run":
        msg = update.notice()
        if msg:
            print(msg)
        return cmd_run(a, ask)
    if a.cmd == "test":
        libs = ["fwd_umi", "fwd_no_umi"] if a.library == "both" else [a.library]
        return selftest.run_selftest(default_install(), a.engine, Path(a.workdir).absolute(), a.max_cpus, a.max_memory,
                                     libs, a.write_expected)
    if a.cmd == "update":
        return cmd_update(a)
    if a.cmd == "bug-report":
        return cmd_bug_report(a)
    p.print_help()
    return CHECK_FAILED


if __name__ == "__main__":
    sys.exit(main())
