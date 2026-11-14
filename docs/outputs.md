# Outputs

One folder per run (`outdir`):

- `counts.tsv`: tab-separated; `gene_id`, `gene_name`, `gene_biotype`, then one column per library in the order of
  the sample list. featureCounts `-s 1 -t exon -g gene_id`: reads on the gene's strand, uniquely aligned, a read
  overlapping two genes not counted.
- `counts.rds`: `readRDS("counts.rds")` gives a `SummarizedExperiment` with the same counts (`assay(se)`), the gene
  annotation (`rowData(se)`: id, name, biotype, chromosome, start, end, strand, length) and the sample list with its
  group column (`colData(se)`).
- `excluded.tsv`: libraries not counted (too few reads after trimming), with the reason.
- `qc/multiqc_report.html`, `qc/samples.tsv`, and the per-tool folders.

## Flags

A flagged library is kept and counted; `flag_reason` in `qc/samples.tsv`, and the report's Lay summary, say in words
which check it missed. The limits are in `schema/qc_thresholds.json`:

- fewer than 500,000 reads counted on genes (both modes);
- fewer than 50% of trimmed reads aligned to a single place in the genome (in the public whole-blood test libraries
  the missing share was ribosomal RNA: see below);
- UMI mode: the UMI spacer (TATA at bases 7-10) in fewer than 50% of reads;
- mode without UMIs: the spacer in more than 5% of reads ("looks like a UMI library"). Libraries without UMIs show it
  in 0.02-0.08% of reads (the 10 public test libraries of PRJNA1262383); a UMI library run in this mode keeps the UMI
  and spacer at the start of its reads and its PCR duplicates are not collapsed.

## Ribosomal RNA

QuantSeq primes reverse transcription on poly(A), so ribosomal RNA, which has no poly(A) tail, should give few
reads. It still gives some, from priming on A-rich stretches inside the 18S and 28S rRNA, and more when the RNA is
degraded. Ensembl (release 116 and earlier) has no gene for the 18S, 28S or 45S rRNA: only the 5.8S copies are genes
of biotype `rRNA`. These reads are therefore missing from the counts and from the Biotype Counts section of the report.
They also align to several places (the rDNA repeats on chromosome 21 and on the unplaced scaffolds GL000220.1 and
KI270733.1), so they lower the share of reads aligned once.

The rRNA check (setting `rrna_check`) measures them. Each library's trimmed reads are aligned with STAR to the
transcribed 45S region of the human rDNA repeat (GenBank U13369.1, bases 1-13,314: 5' ETS, 18S, ITS1, 5.8S, ITS2,
28S, 3' ETS; shipped as `workflow/assets/rdna_45s.fa`), without splicing and with the filters of the main alignment.
Each read is then put in one of four classes, shown per library in the report's "Reads by class" chart: 45S rRNA
(any hit on the 45S, whatever its genome alignment); the other reads aligned to one place in the genome; to several
places; not aligned. `qc/samples.tsv` gives:

- `rrna_45s_share`: 45S rRNA reads as a share of the trimmed reads;
- `mt_rrna_share`: reads whose genome alignment falls on a mitochondrial rRNA gene (Ensembl biotype `Mt_rRNA`), as a
  share of the trimmed reads; NA when the GTF has no such gene.

Neither column flags a library. With `rrna_check: auto` (the standard) the check runs with the `ensembl_115`
reference and not with a custom reference, since the 45S sequence is human; set `rrna_check: true` for a human custom
reference. On one public library (SRR33542394) the 45S share was 43.1% of the trimmed reads; the reads with any
genome alignment on the rDNA loci were 41.9%, and 99.8% of those were also found by the check.
- `run/`: `settings.yaml` (every setting as run), `changes.tsv` (settings changed from the standard), `samples.csv`,
  `versions.tsv`, `containers.tsv` (each process's image and its digest), `trace.txt`, `report.html`, `nextflow.log`,
  and `DONE` once the run has ended without error.
- With `keep_bams` or `keep_trimmed_fastq`: the alignments and trimmed reads in `run/intermediate/`.
