# Installation

`install.sh` puts everything in one folder you choose, without administrator rights:

```bash
bash install.sh --prefix /path/to/quantseq-counts
```

It downloads micromamba 2.9.0 and Nextflow 25.04.8 and checks both against the checksums in `conda/downloads.tsv`,
then builds a small environment (Java 17, Python 3.12, samtools, and udocker on Linux) from the lock file of your
platform (`conda/conda-linux-64.lock` or `conda/conda-osx-arm64.lock`). Supported: Linux x86_64 and macOS arm64.

The analysis tools run in containers pinned in the workflow; the first run downloads them (about 4 GB). With
udocker, and with Docker on a local run, the run pulls every image, one at a time, before it starts. The first
self-test can therefore take half an hour or more (35 minutes with udocker on a server behind a proxy); later runs
reuse the images.

Reference: with `reference: ensembl_115` the first run downloads the Ensembl 115 human genome and annotation into
`reference_dir`, checks them against Ensembl's checksums, and builds the STAR index there (once; it needs about 32 GB of memory).
Later runs on the same `reference_dir` reuse it.

Updates: each run says when a newer release exists. Nothing changes until you type `quantseq-counts update`, which
installs the new version beside the current one; `quantseq-counts --use VERSION ...` runs any installed version, so
a study can end on the version it started with.
