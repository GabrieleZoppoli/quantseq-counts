# Settings

Every setting can be changed in the form, in `quantseq-counts setup` or in `settings.yaml`. The default is the standard; a run lists every change from it on the first page of its quality report.

## Basic settings

| Setting | Default | What it does |
|---|---|---|
| `package_version` | (empty) | Version of quantseq-counts that wrote these settings; a run refuses another version unless told to accept it. |
| `run_name` | (empty) | Short name of this run, used in the report (letters, digits, - and _). |
| `fastq_dir` | (empty) | Folder on the server holding the FASTQ files. |
| `samples` | (empty) | The sample list (samples.csv: sample, fastq, optional group). |
| `outdir` | (empty) | Folder where the results of this run are written; it must not hold a finished run. |
| `library` | `fwd_umi` | Library type: QuantSeq FWD with UMI (fwd_umi) or without UMI (fwd_no_umi). Values: `fwd_umi`, `fwd_no_umi`. |
| `reference` | `ensembl_115` | Human reference: Ensembl 115 downloaded by the package (ensembl_115) or your own files (custom). Values: `ensembl_115`, `custom`. |
| `fasta` | (empty) | Genome FASTA of a custom human reference. |
| `gtf` | (empty) | Gene annotation (GTF) of a custom human reference. |
| `reference_dir` | (empty) | Folder where the reference and its STAR index are kept and reused between runs. |
| `engine` | `apptainer` | Container engine: apptainer (usual on servers without root), udocker, or docker. Values: `apptainer`, `udocker`, `docker`. |
| `executor` | `local` | Where the jobs run: on this server (local) or through a SLURM queue (slurm). Values: `local`, `slurm`. |
| `max_cpus` | `16` | Most cores the run may use at once on this server. |
| `max_memory` | `160 GB` | Most memory the run may use at once on this server (for example 64 GB). |
| `slurm_queue` | (empty) | SLURM partition (queue) to submit to. |
| `slurm_account` | (empty) | SLURM account to charge, if your cluster asks for one. |

## Advanced settings

| Setting | Default | What it does |
|---|---|---|
| `udocker_dir` | (empty) | Folder where udocker keeps its images (empty: inside the installation). |
| `umi_pattern` | `^(?P<umi_1>.{6})(?P<discard_1>.{4}).*` | UMI-tools regular expression: 6 UMI bases, then 4 spacer bases discarded. |
| `dedup_algo` | `dir` | UMICollapse grouping algorithm (dir = directional, as UMI-tools). Values: `dir`, `adj`, `cc`. |
| `trim_adapter` | `AGATCGGAAGAGC` | Adapter sequence removed by Trim Galore. |
| `star_extra_args` | `--outFilterMismatchNoverLmax 0.1 --clip3pAdapterSeq AAAAAAAA` | Extra STAR arguments: mismatch limit and poly(A) clipping, as Lexogen recommends. |
| `star_threads` | (empty) | Threads for STAR (empty: the cores given to the alignment task). |
| `strand` | `forward` | Strand of the reads relative to the gene; QuantSeq FWD reads are forward. Values: `forward`, `reverse`, `unstranded`. **Warning shown when changed:** QuantSeq FWD reads are on the gene's strand: counting them as reverse or unstranded gives wrong counts. |
| `count_multimappers` | `false` | Count reads that align to several places (featureCounts -M). **Warning shown when changed:** Counting reads that align to several places adds reads whose gene is uncertain; the standard drops them. |
| `dedup_without_umi` | `false` | No-UMI libraries only: remove duplicates by position alone. **Warning shown when changed:** Without UMIs, reads at the same position are often different molecules in a 3' library: removing them by position loses real counts. |
| `deterministic_sort` | `true` | Sort alignments by read name, then by position, before deduplication, so reruns give identical counts. **Warning shown when changed:** Without the name-then-position sort, the read kept among duplicates follows thread scheduling: reruns can differ by a few counts. |
| `keep_bams` | `false` | Keep the alignment files (BAM) in the output folder. |
| `keep_trimmed_fastq` | `false` | Keep the trimmed reads in the output folder (used by the release check). |
| `min_trimmed_reads` | `10000` | Libraries with fewer reads after trimming are not aligned and are reported as excluded. |
| `skip_qualimap` | `false` | Skip Qualimap (alignment quality report). |
| `skip_rseqc` | `false` | Skip RSeQC (read distribution and other checks). |
| `skip_dupradar` | `false` | Skip dupRadar (duplication against expression). |
| `rrna_check` | `auto` | Measure the share of reads from 45S ribosomal RNA, against the human 45S sequence (GenBank U13369.1): auto measures it with the ensembl_115 reference and not with a custom one (the columns read NA); true or false turn it on or off. Values: `auto`, `true`, `false`. |
