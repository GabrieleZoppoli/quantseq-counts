# Trimming in the two library modes

Both modes trim the same way; the UMI mode first moves the 6-nt UMI into the read name and removes the 4-nt
spacer (UMI-tools, `^(?P<umi_1>.{6})(?P<discard_1>.{4}).*`).

| Step | What it removes | How |
|---|---|---|
| Trim Galore | Illumina adapter `AGATCGGAAGAGC`, low-quality 3' bases (Phred 20), reads shorter than 20 nt | `--adapter AGATCGGAAGAGC` (other values Trim Galore's defaults) |
| STAR | poly(A) at the 3' end; mismatches at the read start | `--clip3pAdapterSeq AAAAAAAA`, `--outFilterMismatchNoverLmax 0.1`, local alignment (soft-clipping) |

Why no fixed cut of the first 12 bases in the mode without UMI: Lexogen's user guide for QuantSeq 3' mRNA-Seq V2
FWD (191UG444V0112, 14 January 2026, Appendix G, Data Analysis, Trimming; the same text is in the V1 guide
015UG009V0271 of 24 January 2023, Appendix H) explains that second-strand synthesis by random priming leaves more
mismatches in the first 12 nucleotides, and recommends an aligner that soft-clips read ends, such as STAR, naming a
12-nt cut only as the alternative for stricter aligners such as HISAT2. The same section asks for removal of adapter,
poly(A)/poly(T) and low-quality bases and of reads shorter than 20 nt, which the two steps above do.

Lexogen's current FAQ ("What sequences should be trimmed?", retrieved 12 November 2026) gives a three-step cutadapt
command for this; quantseq-counts uses Trim Galore and STAR's poly(A) clipping instead, so that the two modes trim
identically and the UMI mode keeps the trimming of the run it was checked against.
