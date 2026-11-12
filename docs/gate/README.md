# Release gate records

One file per gate run: the comparison table of `tools/release_gate.sh` followed by the object-by-object result of the
comparison of run A with run C (and with run B, on another day). A release needs A = C = B on its test data and a
control (D1 against D2, the name-then-position sort switched off) that differs, which shows that the comparison would
see a change in the reads kept.

- `0.1.0-dev_synthetic.tsv` (12 November 2026, Linux server, udocker): synthetic data (27,512 reads in three
  libraries). A and C identical in all 12 objects. The control did not differ either: with so few reads STAR's
  output order does not vary with the thread count, so this run cannot show that the gate detects a difference; the
  gate is repeated on public libraries of 2 million reads.
- `0.1.0-dev_public.tsv` (12 November 2026, Linux server, udocker, 11:43-13:29 UTC): the three public UMI libraries of
  `tests/data/public/SOURCES.tsv`, first 2,000,000 reads each, against Ensembl 115 chromosome 22. A and C identical in
  all 12 objects (counts, R object, QC table, every pre-deduplication and deduplicated BAM's records, trimmed reads),
  with STAR at 8 and 5 threads, the sorts at 6 and 3 and featureCounts at 6 and 3. The control differed in 9 of 12
  objects: with the name-then-position sort off, the alignments' order and the reads kept followed the thread count,
  and the counts table differed in 2 genes by 1 count each. STAR's records were the same at both thread counts, so
  STAR's thread count is not fixed. Run B (another day) is to come.
