# quantseq-counts

Gene counts, a quality report and a full record of the run from Lexogen QuantSeq 3' mRNA-Seq FWD libraries, with or
without UMIs, on a shared server without administrator rights. The same FASTQ files give the same counts table,
byte for byte, on every rerun, whatever the day, the server load or the number of threads.

## What it does

For each library: a FASTQ check and FastQC; UMI extraction (UMI mode); adapter, poly(A) and quality trimming; STAR
alignment to the human genome; a sort by read name and then by position, so that the order of reads tied on position
does not depend on thread scheduling; UMI deduplication with UMICollapse (UMI mode); counting with featureCounts on
uniquely aligned reads; quality checks (Qualimap, RSeQC, dupRadar, biotypes, a QuantSeq read screen); one MultiQC
report. It stops at counts: normalisation and statistics are left to you, in R.

The tools are those of nf-core/rnaseq 3.26.0, in the same containers and with the same arguments, apart from the
transcriptome quantification (Salmon), which is left out because it cannot be made to give identical results twice.

## Quick start

On the server, as yourself:

```bash
git clone https://github.com/GabrieleZoppoli/quantseq-counts.git
bash quantseq-counts/install.sh --prefix ~/quantseq-counts      # no root; about 1.3 GB, plus about 4 GB of container images at the first run
~/quantseq-counts/bin/quantseq-counts --version
```

Then describe the run, either with the [settings page](https://gabrielezoppoli.github.io/quantseq-counts/) (in
your browser; it writes `settings.yaml` and `samples.csv`) or with questions in the terminal:

```bash
~/quantseq-counts/bin/quantseq-counts setup
~/quantseq-counts/bin/quantseq-counts run --settings settings.yaml --samples samples.csv
```

The run checks every setting and every FASTQ file before it starts, then works in the background; it tells you how to
follow it. Container engines: Apptainer, udocker or Docker. Executors: this server, or SLURM.

## What you get

| File | What it is |
|---|---|
| `counts.tsv` | genes in rows (Ensembl id, name, biotype), libraries in columns: molecule counts |
| `counts.rds` | the same as a `SummarizedExperiment`, with gene annotation and the sample list |
| `excluded.tsv` | libraries not counted (too few reads after trimming), with the reason |
| `qc/multiqc_report.html` | the quality report; its first page lists libraries passed and flagged and any setting changed from the standard |
| `qc/samples.tsv` | per library: reads at each step, shares dropped, the QuantSeq screen, the share of reads from ribosomal RNA, a flag with its reason |
| `run/` | settings as run, tool versions, container images, the Nextflow trace and logs |
| `README.txt` | what each file is, and the two lines of R that load the counts |

These are counts from a 3' library: one read per molecule near the 3' end. Do not compute TPM or FPKM.

## More

- [Settings](docs/settings.md): every setting, its default and what it does.
- [Installation](docs/install.md), [outputs](docs/outputs.md), [when something goes wrong](docs/troubleshooting.md).
- [Trimming in the two library modes](docs/no_umi_trimming.md).
- [Design](docs/design.md): what it leaves out, why reruns are identical, the release gate; [changes](CHANGELOG.md).

## Help

Open an issue on GitHub with the version and the bundle written by `quantseq-counts bug-report <output folder>`
(it replaces sample names, paths and host names; read it before attaching it). Do not paste anything about your
samples.

## Citing

quantseq-counts is archived on Zenodo: [10.5281/zenodo.24380084](https://doi.org/10.5281/zenodo.24380084)
(all versions; version 1.0.0 is [10.5281/zenodo.24380085](https://doi.org/10.5281/zenodo.24380085)). Cite the version
you ran (`package_version` in `run/settings.yaml` of the output folder); `CITATION.cff` gives the reference.

## Licence and credits

MIT (`LICENSE`). The process modules in `workflow/modules/nf-core/` come from nf-core/rnaseq (commit e7ca462, MIT,
`workflow/modules/nf-core/LICENSE-nf-core`); please cite nf-core and the tools listed in `run/versions.tsv`.
