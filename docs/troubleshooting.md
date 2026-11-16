# When something goes wrong

- **The run stops before starting** and names a sample or a file: the sample list and the FASTQ folder disagree, or a
  setting is not valid. Fix the file it names and run again.
- **"holds a finished run"**: choose another `outdir`; a run that ended without error (`run/DONE`) is never overwritten.
- **"holds an unfinished run"**: add `--resume` to continue it (also when `counts.tsv` is there but a later quality step failed).
- **"written by quantseq-counts X, this is Y"**: the settings come from another version. Use that version
  (`--use X`) to keep a study's counts comparable, or add `--accept-version-change`.
- **A library is flagged** on the report's first page: it was counted; the flag says which check it missed.
- **An image could not be pulled, or its digests differ** (udocker): see `run/images.log`. Images are pinned to the digests in
  `workflow/assets/containers.tsv`; a network problem is the usual cause of a failed pull.
- **An image could not be pulled** (Docker): Docker downloads images through its own service, not through your
  session, so a server that reaches the internet through a proxy needs the proxy set for that service too (an
  administrator does it; Docker's documentation calls it the daemon proxy). Without it, set `engine: udocker`, which
  runs as you and uses your proxy settings. Details in `run/images.log`.
- **A step failed**: `quantseq-counts bug-report <outdir>` writes a bundle for a GitHub issue.
