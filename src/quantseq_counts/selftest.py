"""`quantseq-counts test`: runs the bundled public libraries (tests/data/public, against chromosome 22) and compares
the counts with the table stored with the package. Identical tables mean the installation, the engine and the
executor work and give the counts every other installation gives."""

import csv
from pathlib import Path

from . import __version__
from . import settings as st


def _read(p: Path):
    with open(p, newline="") as f:
        rows = list(csv.reader(f, delimiter="\t"))
    return rows[0], {r[0]: r for r in rows[1:]}, [r[0] for r in rows[1:]]


def compare_counts(expected: Path, got: Path) -> tuple[bool, str]:
    he, e, order = _read(expected)
    hg, g, _ = _read(got)
    if he != hg:
        return False, f"different libraries or columns: expected {he[3:] if len(he) > 3 else he[1:]}, got {hg[3:] if len(hg) > 3 else hg[1:]}"
    if set(e) != set(g):
        return False, f"different genes: {len(set(e) ^ set(g))} not in both tables"
    for gene in order:
        for i, col in enumerate(he):
            if e[gene][i] != g[gene][i]:
                return False, f"first difference: gene {gene}, {col}: expected {e[gene][i]}, got {g[gene][i]}"
    libs = len(he) - 3 if he[:3] == ["gene_id", "gene_name", "gene_biotype"] else len(he) - 1
    return True, f"identical: {len(order)} genes, {libs} libraries"


def expected_file(root: Path, library: str) -> Path:
    return Path(root) / "tests" / "data" / "public" / f"expected_counts_{library}.tsv"


def selftest_settings(root: Path, library: str, engine: str, workdir: Path, cpus: int, memory: str):
    pub = Path(root) / "tests" / "data" / "public"
    rows = [r for r in csv.DictReader(open(pub / "SOURCES.tsv"), delimiter="\t") if r["library"] == library]
    workdir = Path(workdir); workdir.mkdir(parents=True, exist_ok=True)
    samples = workdir / f"samples_{library}.csv"
    samples.write_text("sample,fastq,group\n" + "".join(f"{r['run']},{r['run']}.fastq.gz,\n" for r in rows))
    # a finished test run is never reused (the run refuses it); an unfinished one is resumed in place
    out, k = workdir / f"out_{library}", 1
    while (out / "run" / "DONE").exists():
        k += 1; out = workdir / f"out_{library}_{k}"
    s = {"package_version": __version__, "run_name": f"selftest_{library}", "fastq_dir": str(pub),
         "samples": str(samples), "outdir": str(out), "reference": "custom",
         "fasta": str(pub / "reference" / "chr22.fa.gz"), "gtf": str(pub / "reference" / "chr22.gtf.gz"),
         "reference_dir": str(workdir / "reference"), "library": library, "engine": engine,
         "max_cpus": cpus, "max_memory": memory, "min_trimmed_reads": 0}
    return s, samples


def _run(argv, ask=None):
    from .cli import main
    return main(argv)


def run_selftest(root: Path, engine: str, workdir: Path, cpus: int, memory: str, libraries, write_expected=False) -> int:
    rc = 0
    for lib in libraries:
        s, samples = selftest_settings(root, lib, engine, workdir, cpus, memory)
        sfile = Path(workdir) / f"settings_{lib}.yaml"
        sfile.write_text(st.dump_settings(s))
        if _run(["run", "--settings", str(sfile), "--samples", str(samples), "--yes", "--foreground"]) != 0:
            log = Path(s["outdir"]) / "run" / "nextflow.log"
            print(f"{lib}: the run failed (see {log})" if log.exists()
                  else f"{lib}: the run did not start (the reason is above)")
            rc = 1
            continue
        got = Path(s["outdir"]) / "counts.tsv"
        exp = expected_file(root, lib)
        if write_expected:
            exp.write_bytes(got.read_bytes()); print(f"{lib}: wrote {exp}")
            continue
        ok, msg = compare_counts(exp, got)
        print(f"{lib}: {msg}")
        rc = rc or (0 if ok else 1)
    if write_expected:
        print("expected counts written; nothing was compared" if rc == 0 else "TEST FAILED")
    else:
        print("installation works: the counts are those every installation gives" if rc == 0 else "TEST FAILED")
    return rc
