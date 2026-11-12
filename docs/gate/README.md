# Release gate records

One file per gate run: the comparison table of `tools/release_gate.sh` followed by the object-by-object result of the
comparison of run A with run C (and with run B, on another day). A release needs A = C = B on its test data and a
control (D1 against D2, the name-then-position sort switched off) that differs, which shows that the comparison would
see a change in the reads kept.

- `0.1.0-dev_synthetic.tsv` (12 November 2026, Linux server, udocker): synthetic data (27,512 reads in three
  libraries). A and C identical in all 12 objects. The control did not differ either: with so few reads STAR's
  output order does not vary with the thread count, so this run cannot show that the gate detects a difference; the
  gate is repeated on public libraries of 2 million reads.
