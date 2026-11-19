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
  the package leaves STAR's thread count free (`star_threads` empty by default). Superseded by the 1.0.0 records below, which include run B.
- `1.0.0_public_3daa97f.tsv` (15 and 16 November 2026, Linux server, udocker; code of commit 3daa97f): the same
  public data and reference as `0.1.0-dev_public.tsv`. Runs A, C, D1 and D2 on 15 November (14:15-17:24 UTC), run B
  on 16 November (07:18-08:06 UTC). A, B and C identical in all 12 objects; the control differed in 9 of 12 (the
  trimmed reads were the same). Gate passed. Superseded by `1.0.0_public.tsv`, run on the release commit itself.
- `1.0.0_public.tsv` (17 and 18 November 2026, Linux server, udocker; commit fbe1d30, from a fresh install): the same
  public data and reference. Runs A, C, D1 and D2 on 17 November (10:21-12:59 UTC), run B on 18 November
  (07:10-07:31 UTC). A, B and C identical in all 12 objects; the control differed in 9 of 12 (the trimmed reads were
  the same). Gate passed. The tagged commit v1.0.0 follows fbe1d30 and changes only this folder, `CHANGELOG.md` and
  `CITATION.cff` (release date).
- Non-public libraries (16 and 17 November 2026, Linux server, udocker): the same gate on three whole-blood libraries
  of the study the package was written for, which are not published. Runs A and C on 16 November (commit bb51729,
  whose workflow is that of fbe1d30), run B on 17 November from a fresh install of fbe1d30. A, B and C identical in
  all 12 objects. Only the result is recorded here.
