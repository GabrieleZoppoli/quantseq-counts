# Public test data

Five public QuantSeq FWD libraries (`SOURCES.tsv`: three with UMI, two without), each cut to 100,000 reads by
`tools/make_public_test_data.sh`: the first 2,000,000 reads of the run were aligned to Ensembl 115 chromosome 22, and
the reads aligned there plus 5% of the others were kept, in file order (seed 20261112). `reference/` holds chromosome
22 and its genes from Ensembl 115.

Because the reads come from the whole genome and the reference is one chromosome, many align to several places and
are not counted, and the brain libraries are nuclear RNA with many intronic reads: only a few thousand reads per
library are counted. The data are for checking that an installation runs and gives the stored counts
(`expected_counts_fwd_umi.tsv`, `expected_counts_fwd_no_umi.tsv`, written on a Linux server with udocker on
12 November 2026), not for biology.

The archives' terms (INSDC): free and unrestricted access; cite the studies in `SOURCES.tsv`.
