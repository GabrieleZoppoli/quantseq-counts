#!/usr/bin/env python3
"""Writes a small synthetic QuantSeq FWD (UMI) data set, the same bytes every time (fixed seed, gzip mtime 0):
a random two-chromosome genome, a GTF of 24 genes on both strands (some with two exons, one pair of genes sharing
an identical 3' end so that reads align to two places), and three libraries of reads taken from the 3' ends of the
genes, each read = 6-nt UMI + TATA + insert, running into poly(A) and the adapter when the insert reaches the end.
Many reads share position and UMI (PCR duplicates) and many share position with different UMIs, so that
deduplication and the order of tied reads are exercised. Usage: make_synthetic_data.py OUTDIR
"""
import gzip
import random
import sys
from pathlib import Path

SEED = 20261112
READ_LEN = 75
ADAPTER = "AGATCGGAAGAGCACACGTCTGAACTCCAGTCAC"
COMP = str.maketrans("ACGT", "TGCA")


def rc(s):
    return s.translate(COMP)[::-1]


def gz_write(path, text):
    with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as f:
        f.write(text.encode())


def main(out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(SEED)
    chroms = {c: "".join(rnd.choice("ACGT") for _ in range(120_000)) for c in ("chrA", "chrB")}
    # a 600-nt 3' end copied from chrA to chrB: reads there align to two places
    seg = chroms["chrA"][20_400:21_000]
    chroms["chrB"] = chroms["chrB"][:80_400] + seg + chroms["chrB"][81_000:]
    genes, gtf = [], []
    for i in range(24):
        c = "chrA" if i < 12 else "chrB"
        start = 2_000 + (i % 12) * 9_000 if i not in (2, 21) else (19_000 if i == 2 else 79_000)
        strand = "+" if i % 3 else "-"
        if i in (2, 21):
            strand = "+"
        two = i % 4 == 0 and i not in (2, 21)
        exons = [(start, start + 400), (start + 1_400, start + 2_000)] if two else [(start, start + 2_000)]
        gid, tid = f"GSYN{i:04d}", f"TSYN{i:04d}"
        biotype = "lncRNA" if i % 7 == 6 else "protein_coding"
        attr = f'gene_id "{gid}"; gene_name "SYN{i}"; gene_biotype "{biotype}";'
        lo, hi = exons[0][0], exons[-1][1]
        gtf.append(f"{c}\tsynthetic\tgene\t{lo + 1}\t{hi}\t.\t{strand}\t.\t{attr}")
        gtf.append(f'{c}\tsynthetic\ttranscript\t{lo + 1}\t{hi}\t.\t{strand}\t.\t{attr} transcript_id "{tid}";')
        for n, (a, b) in enumerate(exons, 1):
            gtf.append(f'{c}\tsynthetic\texon\t{a + 1}\t{b}\t.\t{strand}\t.\t{attr} transcript_id "{tid}"; exon_number "{n}";')
        seq = "".join(chroms[c][a:b] for a, b in exons)
        genes.append(seq if strand == "+" else rc(seq))
    fa = "".join(f">{c}\n" + "\n".join(s[k:k + 60] for k in range(0, len(s), 60)) + "\n" for c, s in chroms.items())
    gz_write(out / "genome.fa.gz", fa)
    gz_write(out / "genes.gtf.gz", "\n".join(gtf) + "\n")
    rows = ["sample,fastq,group"]
    for lib in (1, 2, 3):
        recs, n = [], 0
        weights = [rnd.randint(1, 40) for _ in genes]
        for g, w in zip(genes, weights):
            for _ in range(w * 12):
                # few distinct start sites per gene: many reads tie on position
                start = len(g) - rnd.choice((90, 120, 150, 200, 260))
                umi = "".join(rnd.choice("ACGT") for _ in range(6)) if rnd.random() < 0.7 else "ACGTAC"
                for _dup in range(rnd.choice((1, 1, 1, 2, 3))):
                    insert = (g[start:] + "A" * 30 + ADAPTER)[: READ_LEN - 10]
                    seq = umi + "TATA" + insert
                    n += 1
                    recs.append(f"@syn{lib}_{n:06d}\n{seq}\n+\n{'I' * len(seq)}\n")
        rnd.shuffle(recs)
        gz_write(out / f"S{lib}.fastq.gz", "".join(recs))
        rows.append(f"S{lib},S{lib}.fastq.gz,{'a' if lib < 3 else 'b'}")
    (out / "samples.csv").write_text("\n".join(rows) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
