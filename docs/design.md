# Design

What the package is for, what it leaves out, and why its counts are the same on every rerun.

## Purpose

A colleague with new QuantSeq FWD libraries, or someone helping them, gets gene counts and quality checks from the
FASTQ files on a shared server without administrator rights, with two commands over ssh and no other help. The
package stops at counts: normalisation, filtering and statistics are left to the user, in R.

Requirements:

- the same input gives the same counts table, byte for byte, whatever the day, the server load or the thread count;
- every setting of a run is recorded in its output, and every change from the standard is listed on the first page of
  its quality report;
- a run does not start when the sample list and the FASTQ folder disagree;
- an update never changes the counts of a study half-way: a new version is installed beside the old one and used only
  when asked for.

Out of scope: species other than human (a newer Ensembl release or a local human reference can be used), other
chemistries (QuantSeq REV, full-length kits, paired-end reads), and anything after the counts.

## Setting up a run

Two routes write the same two files, `settings.yaml` and `samples.csv`: the [settings page](index.html), which runs
only in the browser and sends nothing anywhere, and `quantseq-counts setup`, which asks the same questions on the
server and checks each answer there. Whichever route made them, `quantseq-counts run` repeats every check before
anything starts: the folder exists, every file in the sample list is there and readable, and the first reads of each
file are looked at to see whether they carry the UMI spacer (a warning when that disagrees with the library mode).

Every setting can be changed. Changes known to make 3' counts wrong (reverse strand, counting multimapping reads,
deduplication without UMIs) are allowed after a plain warning.

## The pipeline

Per library: FASTQ check; FastQC; UMI extraction (UMI mode); adapter, poly(A) and quality trimming; STAR alignment to
the genome; a sort by read name and then a stable sort by position; UMI deduplication with UMICollapse (UMI mode);
featureCounts (`-s 1 -t exon -g gene_id`, uniquely aligned reads only, a read overlapping two genes not counted);
quality checks (Qualimap, RSeQC, dupRadar, the featureCounts biotype summary, a QuantSeq read screen, and, with the
Ensembl reference, the share of reads from the 45S ribosomal RNA); one MultiQC report. The strand is set to forward,
not inferred.

The process modules, containers and arguments are those of nf-core/rnaseq 3.26.0 (commit e7ca462, copied with their
licence). The package is its own small Nextflow workflow (Nextflow 25.04.8) because nf-core/rnaseq has no setting that
runs STAR without Salmon and a configuration file cannot add a process. Salmon, STAR's transcriptome output and the
transcriptome deduplication are left out: they cannot be made to give identical results twice, and the counts come
from the genome alignments.

## Why the counts are the same on every rerun

- STAR writes the same alignments on every run, but in an order that follows thread scheduling.
- `samtools sort` keeps reads tied on chromosome, position and strand in the order it receives them.
- Among duplicates of equal mapping quality, UMICollapse keeps one by its place in that order; STAR's mapping quality
  takes only four values, so ties are common.
- The read kept, and sometimes a count, would therefore follow the thread order. Sorting by read name first, then
  stably by position, makes the order depend on the read names only. featureCounts adds integers, so its own thread
  count does not matter. No random seed and no single-threaded STAR are needed.

The `deterministic_sort` setting switches the name sort off; the release gate uses that to show that its comparison
does see the difference.

## Release gate

No release unless, on the test data:

- three fresh runs, none resumed, are identical object by object: the standard run (A), the same run on another day
  (B) and a run with other thread counts for STAR, the sorts, Trim Galore and featureCounts (C). The objects are
  `counts.tsv`, `counts.rds`, `qc/samples.tsv`, the records of every BAM before and after deduplication, and the
  decompressed trimmed reads;
- the same pair of thread counts with the name sort switched off (D1, D2) gives different results, so the comparison
  is seen to catch a change.

Files that carry dates or paths (report pages, logs, BAM headers) are compared on their content. `tools/release_gate.sh`
runs the gate on a server; the records are in [docs/gate/](gate/README.md). On GitHub's test machines every push runs A
against C with Docker and Apptainer in both library modes, the SLURM executor on a one-machine SLURM, and every
executed command against the arguments of the reference run.

## Distribution

Public GitHub repository, MIT licence (nf-core's MIT notice kept on the copied modules), versioned releases with a
DOI through Zenodo. Help through GitHub issues, with a bundle written by `quantseq-counts bug-report`, which replaces
sample names with S01, S02 and so on and removes paths and host names.
