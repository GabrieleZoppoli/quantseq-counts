#!/usr/bin/env Rscript
# The run's main outputs from featureCounts: counts.tsv (genes x libraries, with gene name and biotype from the GTF),
# counts.rds (a SummarizedExperiment with the same counts, gene annotation and the sample list), README.txt and
# excluded.tsv. Libraries are in sample-list order and genes in GTF order, written the same way every time, so that
# equal counts give equal files.
# Usage: build_outputs.R --fc featurecounts.txt --gtf genes.gtf --samples samples.csv --excluded excluded.tsv
#                        --version X.Y.Z --out DIR
invisible(Sys.setlocale("LC_ALL", "C"))  # the RDS header records the locale's encoding: fix it, so equal counts give equal bytes
suppressPackageStartupMessages(library(SummarizedExperiment))
a <- commandArgs(trailingOnly = TRUE)
arg <- function(k) { i <- match(paste0("--", k), a); if (is.na(i)) stop("missing --", k); a[i + 1] }
out <- arg("out"); dir.create(out, showWarnings = FALSE, recursive = TRUE)

fc <- read.delim(arg("fc"), comment.char = "#", check.names = FALSE, colClasses = "character")
libs <- sub("\\.bam$", "", colnames(fc)[-(1:6)])
samples <- read.csv(arg("samples"), colClasses = "character", strip.white = TRUE)
ex_file <- arg("excluded")
excluded <- if (file.exists(ex_file) && file.size(ex_file) > 0) read.delim(ex_file, header = FALSE, colClasses = "character",
  col.names = c("sample", "reason")) else data.frame(sample = character(), reason = character())
keep <- samples$sample[samples$sample %in% libs]
missing <- setdiff(samples$sample, c(libs, excluded$sample))
if (length(missing)) stop("libraries in the sample list but neither counted nor excluded: ", paste(missing, collapse = ", "))
if (!length(keep)) stop("no library of the sample list was counted (the featureCounts columns are ", paste(libs, collapse = ", "), ")")

# genes from the exon lines (the filtered GTF of the run keeps no gene lines), in order of first appearance
gtf <- read.delim(arg("gtf"), header = FALSE, comment.char = "#", colClasses = "character", quote = "")
ex <- gtf[gtf$V3 == "exon", ]
attr1 <- function(x, key) { m <- regmatches(x, regexpr(paste0(key, ' "[^"]*"'), x)); v <- rep(NA_character_, length(x))
  has <- grepl(paste0(key, ' "'), x); v[has] <- sub(paste0(key, ' "([^"]*)"'), "\\1", m); v }
gid <- attr1(ex$V9, "gene_id")
first <- !duplicated(gid)
ann <- data.frame(gene_id = gid[first], gene_name = attr1(ex$V9[first], "gene_name"),
                  gene_biotype = attr1(ex$V9[first], "gene_biotype"), chromosome = ex$V1[first],
                  start = as.integer(tapply(as.integer(ex$V4), factor(gid, levels = gid[first]), min)),
                  end = as.integer(tapply(as.integer(ex$V5), factor(gid, levels = gid[first]), max)),
                  strand = ex$V7[first], stringsAsFactors = FALSE)
fc <- fc[order(match(fc$Geneid, ann$gene_id)), ]
counts <- sapply(keep, function(s) as.integer(fc[[paste0(s, ".bam")]]))
counts <- matrix(counts, nrow = nrow(fc), dimnames = list(fc$Geneid, keep))
rows <- ann[match(fc$Geneid, ann$gene_id), ]
rows$length <- as.integer(fc$Length)

tab <- data.frame(gene_id = rows$gene_id, gene_name = ifelse(is.na(rows$gene_name), "", rows$gene_name),
                  gene_biotype = ifelse(is.na(rows$gene_biotype), "", rows$gene_biotype), counts,
                  check.names = FALSE, stringsAsFactors = FALSE)
con <- file(file.path(out, "counts.tsv"), "wb")
writeLines(paste(colnames(tab), collapse = "\t"), con, sep = "\n")
writeLines(do.call(paste, c(lapply(tab, function(x) if (is.integer(x)) format(x, scientific = FALSE, trim = TRUE) else x),
                            sep = "\t")), con, sep = "\n")
close(con)

cd <- samples[match(keep, samples$sample), setdiff(colnames(samples), "fastq"), drop = FALSE]
rownames(cd) <- cd$sample
se <- SummarizedExperiment(assays = list(counts = counts), rowData = S4Vectors::DataFrame(rows, row.names = rows$gene_id),
                           colData = S4Vectors::DataFrame(cd, check.names = FALSE),
                           metadata = list(quantseq_counts_version = arg("version")))
saveRDS(se, file.path(out, "counts.rds"))

write.table(excluded, file.path(out, "excluded.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)
ex_lines <- if (nrow(excluded)) paste0("  ", excluded$sample, ": ", excluded$reason) else "  none"
readme <- c(
  paste0("quantseq-counts ", arg("version"), ": gene counts of ", length(keep), " libraries."),
  "",
  "counts.tsv          genes in rows (Ensembl id, gene name, biotype), libraries in columns; molecule counts",
  "counts.rds          the same counts as a SummarizedExperiment, with the gene annotation and the sample list",
  "excluded.tsv        libraries not counted, with the reason",
  "qc/                 quality report (multiqc_report.html) and per-library table (samples.tsv)",
  "run/                settings as run, tool versions, containers, the Nextflow trace and logs",
  "",
  "In R:",
  "  se <- readRDS(\"counts.rds\")",
  "  counts <- SummarizedExperiment::assay(se)",
  "",
  "These are molecule counts from a 3' library: do not compute TPM or FPKM (each molecule gives one read",
  "near the 3' end, whatever the length of the transcript).",
  "",
  "Libraries excluded:", ex_lines)
writeLines(readme, file.path(out, "README.txt"))
