#!/usr/bin/env python3
"""Cuts a public FASTQ down to test size: the reads that aligned to the test reference plus a fixed random share
of the others (so the test also meets reads that do not align), in file order, up to --max-reads, written the same
way every time (fixed seed, gzip mtime 0). Read names are matched on their first word, without the _UMI suffix
that UMI-tools adds. Usage: cut_test_data.py --fastq IN --aligned NAMES --max-reads N --other-share F --seed S --out OUT"""
import argparse
import gzip
import random
import re


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fastq", required=True); ap.add_argument("--aligned", required=True)
    ap.add_argument("--max-reads", type=int, required=True); ap.add_argument("--other-share", type=float, required=True)
    ap.add_argument("--seed", type=int, required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    aligned = {re.sub(r"_[ACGTN]+$", "", l.strip()) for l in open(a.aligned) if l.strip()}
    rnd = random.Random(a.seed)
    kept = 0
    with gzip.open(a.fastq, "rt") as f, open(a.out, "wb") as raw, \
            gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as out:
        while kept < a.max_reads:
            rec = [f.readline() for _ in range(4)]
            if not rec[0]:
                break
            name = rec[0][1:].split()[0]
            draw = rnd.random()  # drawn for every read, so the choice of one read never shifts the others
            if name in aligned or draw < a.other_share:
                out.write("".join(rec).encode())
                kept += 1


if __name__ == "__main__":
    main()
