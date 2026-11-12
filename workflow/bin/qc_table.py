#!/usr/bin/env python3
"""qc/samples.tsv (reads at each stage, shares, the QuantSeq screen, a flag with its reason) and the first page
of the quality report (summary_mqc.html) for the biologist: libraries passed and flagged, libraries excluded, and
the settings that differ from the standard. Python standard library only.
Usage: qc_table.py --dir FOLDER --library fwd_umi|fwd_no_umi --thresholds thresholds.json --changes changes.tsv
                   --excluded excluded.tsv --out OUTDIR
FOLDER holds <lib>.Log.final.out, <lib>*_trimming_report.txt, <lib>.umi_dedup.sorted.bam.flagstat (UMI mode),
screen.tsv and featurecounts.txt.summary."""
import argparse
import html
import json
import re
from pathlib import Path


def star(path):
    v = {}
    for line in path.read_text().splitlines():
        if "|" in line:
            k, _, x = line.partition("|")
            v[k.strip()] = x.strip()
    return int(v["Uniquely mapped reads number"]), int(v["Number of reads mapped to multiple loci"])


def trimmed(path):
    t = path.read_text()
    total = float(re.search(r"([\d.]+)\ssequences processed in total", t).group(1))
    m = re.search(r"shorter than the length cutoff[^:]+:\s*([\d.]+)", t)
    return int(total - (float(m.group(1)) if m else 0))


def flagstat_primary(path):
    m = re.search(r"^(\d+) \+ \d+ primary mapped", path.read_text(), re.M)
    return int(m.group(1))


def table(path):
    rows = [l.split("\t") for l in path.read_text().splitlines() if l.strip()]
    return rows[0], rows[1:]


def main():
    ap = argparse.ArgumentParser()
    for k in ("dir", "library", "thresholds", "changes", "excluded", "out"):
        ap.add_argument("--" + k, required=True)
    a = ap.parse_args()
    d, out = Path(a.dir), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    umi = a.library == "fwd_umi"
    th = json.loads(Path(a.thresholds).read_text())
    head, srows = table(d / "screen.tsv")
    screen = {r[0]: dict(zip(head, r)) for r in srows}
    fh, frows = table(d / "featurecounts.txt.summary")
    libs = [c[:-4] if c.endswith(".bam") else c for c in fh[1:]]
    fc = {lib: {r[0]: int(r[i + 1]) for r in frows} for i, lib in enumerate(libs)}
    cols = ["library", "raw", "trimmed", "aligned_unique", "aligned_multi", "after_dedup", "counted",
            "share_multimapping", "share_ambiguous", "umi_spacer_share", "umi_with_n_share", "polyA8_share",
            "adapter_share", "flag", "flag_reason"]
    lines, passed, flagged = ["\t".join(cols)], [], []
    for lib in sorted(libs):
        sc = screen[lib]
        raw = int(sc["reads"])
        uni, multi = star(d / f"{lib}.Log.final.out")
        trim = trimmed(next(d.glob(f"{lib}_*trimming_report.txt")))
        dedup = flagstat_primary(d / f"{lib}.umi_dedup.sorted.bam.flagstat") if umi else None
        f = fc[lib]
        total_fc = sum(f.values()) or 1
        counted = f.get("Assigned", 0)
        sh = lambda k: int(sc[k]) / raw if raw else 0.0
        reasons = []
        if counted < th.get("min_assigned_reads", 0):
            reasons.append(f"counted {counted} < {th['min_assigned_reads']}")
        if trim and uni / trim < th.get("min_unique_share", 0):
            reasons.append(f"uniquely aligned {100 * uni / trim:.1f}% of trimmed reads < {100 * th['min_unique_share']:.1f}%")
        if umi and sh("tata_exact") < th.get("min_umi_spacer_share", 0):
            reasons.append(f"UMI spacer in {100 * sh('tata_exact'):.1f}% of reads < {100 * th['min_umi_spacer_share']:.1f}%")
        flag = "flagged" if reasons else "pass"
        (flagged if reasons else passed).append((lib, "; ".join(reasons)))
        vals = [lib, raw, trim, uni, multi, "" if dedup is None else dedup, counted,
                f"{f.get('Unassigned_MultiMapping', 0) / total_fc:.4f}", f"{f.get('Unassigned_Ambiguity', 0) / total_fc:.4f}",
                f"{sh('tata_exact'):.4f}", f"{sh('umi_with_n'):.4f}", f"{sh('polyA8_any'):.4f}", f"{sh('adapter12_any'):.4f}",
                flag, "; ".join(reasons)]
        lines.append("\t".join(map(str, vals)))
    (out / "samples.tsv").write_text("\n".join(lines) + "\n")

    _, changes = table(Path(a.changes))
    eh, erows = table(Path(a.excluded)) if Path(a.excluded).exists() else ([], [])
    erows = [r for r in erows if r and r[0] != "sample"]
    e = html.escape
    page = [f"<p><b>{len(passed)} of {len(libs)} libraries passed</b> the checks"
            + (f"; {len(flagged)} flagged:</p><ul>" + "".join(f"<li>{e(l)}: {e(r)}</li>" for l, r in flagged) + "</ul>"
               if flagged else ".</p>")]
    if erows:
        page.append(f"<p>{len(erows)} not counted:</p><ul>" + "".join(f"<li>{e(r[0])}: {e(r[1])}</li>" for r in erows) + "</ul>")
    if changes:
        page.append("<p>This run differs from the standard in:</p><ul>"
                    + "".join(f"<li>{e(k)}: {e(v)} (standard: {e(s)})</li>" for k, s, v in changes) + "</ul>")
    else:
        page.append("<p>This run used the standard settings.</p>")
    header = ("<!--\nid: 'quantseq_summary'\nsection_name: 'Summary for the biologist'\n-->\n")
    (out / "summary_mqc.html").write_text(header + "\n".join(page) + "\n")


if __name__ == "__main__":
    main()
