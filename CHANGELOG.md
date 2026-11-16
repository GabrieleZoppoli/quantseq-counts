# Changelog

## 1.0.0 (2026-11-16)

First release.

- Gene counts (`counts.tsv`, `counts.rds`), a quality report and a record of the run from QuantSeq 3' mRNA-Seq FWD
  libraries, with UMIs (default) or without.
- Identical counts on every rerun: reads sorted by name and then stably by position before deduplication. Release
  gate passed on public libraries: runs on two days and at two sets of thread counts identical in every object; the
  control with the sort off differs (`docs/gate/`).
- Set-up from the settings page or from `quantseq-counts setup`; every setting checked, with the FASTQ files, before
  a run starts.
- Containers: Apptainer, udocker, Docker. Executors: local, SLURM (job limits `max_cpus`, `max_memory`, `max_time`).
- Reference: Ensembl 115 human, downloaded and checked by the package, or a human FASTA and GTF of your own.
- Quality table `qc/samples.tsv` with reads at each step, the QuantSeq read screen, the shares of 45S and
  mitochondrial ribosomal RNA (Ensembl reference), and warning flags with their reasons: fewer than 500,000 reads
  counted, fewer than 50% of trimmed reads aligned once, UMI spacer in fewer than 75% of reads (UMI mode) or in more
  than 5% (mode without UMIs). Flagged libraries are kept and counted.
- Container images checked before the run starts, with Docker as with udocker, so that an image that cannot be
  downloaded (for example from behind a proxy) stops the run at once with the reason.
- `quantseq-counts test` (bundled public data), `update` (new versions installed beside the old), `bug-report`.
