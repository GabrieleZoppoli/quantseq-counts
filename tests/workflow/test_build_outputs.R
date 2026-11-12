# Test of workflow/bin/build_outputs.R on made-up featureCounts output.
# Usage: Rscript tests/workflow/test_build_outputs.R   (from the repository root; needs SummarizedExperiment)
suppressPackageStartupMessages(library(SummarizedExperiment))
script <- normalizePath(file.path("workflow", "bin", "build_outputs.R"))
fails <- 0
ok <- function(cond, what) { cat(if (isTRUE(cond)) "ok - " else { fails <<- fails + 1; "FAIL - " }, what, "\n", sep = "") }
d <- tempfile(); dir.create(d)
writeLines(c(
  '1\tsyn\tgene\t1\t100\t.\t+\t.\tgene_id "G2"; gene_name "TWO"; gene_biotype "protein_coding";',
  '1\tsyn\texon\t1\t100\t.\t+\t.\tgene_id "G2"; gene_name "TWO"; gene_biotype "protein_coding"; transcript_id "T2";',
  '1\tsyn\tgene\t200\t300\t.\t-\t.\tgene_id "G1"; gene_biotype "lncRNA";',
  '1\tsyn\texon\t200\t300\t.\t-\t.\tgene_id "G1"; gene_biotype "lncRNA"; transcript_id "T1";'), file.path(d, "genes.gtf"))
# featureCounts columns come in the order the BAMs were given, not the sample-list order
writeLines(c('# Program:featureCounts v2.0.6; Command:"featureCounts" ...',
  "Geneid\tChr\tStart\tEnd\tStrand\tLength\tS3.bam\tS1.bam",
  "G2\t1\t1\t100\t+\t100\t5\t1000000", "G1\t1\t200\t300\t-\t101\t0\t7"), file.path(d, "fc.txt"))
writeLines(c("Status\tS3.bam\tS1.bam", "Assigned\t5\t1000007", "Unassigned_MultiMapping\t1\t2"), file.path(d, "fc.txt.summary"))
writeLines(c("sample,fastq,group", "S1,a.fq.gz,case", "S2,b.fq.gz,ctrl", "S3,c.fq.gz,ctrl"), file.path(d, "samples.csv"))
writeLines("S2\tfewer than 10000 reads after trimming (12)", file.path(d, "excluded.tsv"))
run <- function(out) system2(file.path(R.home("bin"), "Rscript"), c(shQuote(script), "--fc", file.path(d, "fc.txt"), "--gtf", file.path(d, "genes.gtf"),
  "--samples", file.path(d, "samples.csv"), "--excluded", file.path(d, "excluded.tsv"), "--version", "9.9.9",
  "--out", out), stdout = TRUE, stderr = TRUE)
r1 <- run(file.path(d, "o1")); r2 <- run(file.path(d, "o2"))
tsv <- readLines(file.path(d, "o1", "counts.tsv"))
ok(identical(tsv[1], "gene_id\tgene_name\tgene_biotype\tS1\tS3"), "header in sample-list order, excluded sample absent")
ok(identical(tsv[2:3], c("G2\tTWO\tprotein_coding\t1000000\t5", "G1\t\tlncRNA\t7\t0")), "rows in GTF order, no scientific notation, empty name")
se <- readRDS(file.path(d, "o1", "counts.rds"))
ok(identical(colnames(se), c("S1", "S3")) && identical(unname(assay(se)[, "S1"]), c(1000000L, 7L)), "rds holds the same integer counts")
ok(identical(as.character(colData(se)$group), c("case", "ctrl")), "rds colData has the group")
ok(identical(rowData(se)$gene_biotype, c("protein_coding", "lncRNA")) && identical(rowData(se)$length, c(100L, 101L)), "rds rowData from the GTF and featureCounts")
ok(identical(S4Vectors::metadata(se)$quantseq_counts_version, "9.9.9"), "rds records the package version")
md5 <- function(o) unname(tools::md5sum(file.path(d, o, c("counts.tsv", "counts.rds"))))
ok(identical(md5("o1"), md5("o2")), "two runs give the same bytes")
rd <- readLines(file.path(d, "o1", "README.txt"))
ok(any(grepl("9.9.9", rd)) && any(grepl("readRDS", rd)) && any(grepl("TPM", rd)), "README names the version, the R lines and the 3' warning")
ok(any(grepl("S2", rd) & grepl("fewer than 10000", rd)), "README lists the excluded library with its reason")
ok(file.exists(file.path(d, "o1", "excluded.tsv")), "excluded.tsv written")
# a GTF without gene lines (nf-core's GTF filter keeps only lines with a transcript_id)
g <- readLines(file.path(d, "genes.gtf")); writeLines(g[grepl("\texon\t", g)], file.path(d, "exons.gtf"))
system2(file.path(R.home("bin"), "Rscript"), c(shQuote(script), "--fc", file.path(d, "fc.txt"), "--gtf", file.path(d, "exons.gtf"),
  "--samples", file.path(d, "samples.csv"), "--excluded", file.path(d, "excluded.tsv"), "--version", "9.9.9",
  "--out", file.path(d, "o3")), stdout = TRUE, stderr = TRUE)
ok(identical(readLines(file.path(d, "o3", "counts.tsv")), tsv), "same table from a GTF with exon lines only")
se3 <- readRDS(file.path(d, "o3", "counts.rds"))
ok(identical(rowData(se3)$start, c(1L, 200L)) && identical(rowData(se3)$strand, c("+", "-")), "gene coordinates from the exons")
# no listed library among the counted ones: stop, never write an empty table
writeLines(c("sample,fastq,group", "X1,x.fq.gz,"), file.path(d, "samples_none.csv"))
r <- system2(file.path(R.home("bin"), "Rscript"), c(shQuote(script), "--fc", file.path(d, "fc.txt"), "--gtf", file.path(d, "genes.gtf"),
  "--samples", file.path(d, "samples_none.csv"), "--excluded", file.path(d, "no_such.tsv"), "--version", "9.9.9",
  "--out", file.path(d, "o4")), stdout = TRUE, stderr = TRUE)
ok(!is.null(attr(r, "status")) && attr(r, "status") != 0 && !file.exists(file.path(d, "o4", "counts.tsv")), "no listed library counted: error, no table")
# the same bytes whatever the locale of the container
runl <- function(out, loc) system2("env", c(paste0("LC_ALL=", loc), paste0("LANG=", loc), file.path(R.home("bin"), "Rscript"),
  shQuote(script), "--fc", file.path(d, "fc.txt"), "--gtf", file.path(d, "genes.gtf"), "--samples", file.path(d, "samples.csv"),
  "--excluded", file.path(d, "excluded.tsv"), "--version", "9.9.9", "--out", file.path(d, out)), stdout = TRUE, stderr = TRUE)
runl("o5", "C"); runl("o6", "en_US.UTF-8")
ok(identical(md5("o5"), md5("o6")), "counts.tsv and counts.rds equal under the C and a UTF-8 locale")
cat(if (fails == 0) "RESULT: PASS\n" else "RESULT: FAIL\n"); quit(status = as.integer(fails > 0))
