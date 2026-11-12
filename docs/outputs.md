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
- `run/`: `settings.yaml` (every setting as run), `changes.tsv` (settings changed from the standard), `samples.csv`,
  `versions.tsv`, `containers.tsv`, `trace.txt`, `report.html`, `nextflow.log`.
- With `keep_bams` or `keep_trimmed_fastq`: the alignments and trimmed reads in `run/intermediate/`.
