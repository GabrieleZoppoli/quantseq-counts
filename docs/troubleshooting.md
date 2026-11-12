# When something goes wrong

- **The run stops before starting** and names a sample or a file: the sample list and the FASTQ folder disagree, or a
  setting is not valid. Fix the file it names and run again.
- **"holds a finished run"**: choose another `outdir`; a finished run is never overwritten.
- **"holds an unfinished run"**: add `--resume` to continue it.
- **"written by quantseq-counts X, this is Y"**: the settings come from another version. Use that version
  (`--use X`) to keep a study's counts comparable, or add `--accept-version-change`.
- **A library is flagged** on the report's first page: it was counted; the flag says which check it missed.
- **An image could not be pulled** (udocker): see `run/images.log`; a network problem is the usual cause.
- **A step failed**: `quantseq-counts bug-report <outdir>` writes a bundle for a GitHub issue.
