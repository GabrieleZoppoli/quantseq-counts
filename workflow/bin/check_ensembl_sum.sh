#!/usr/bin/env bash
# Checks a file downloaded from Ensembl against the release's CHECKSUMS file (BSD `sum`: checksum and 1K blocks).
# Usage: check_ensembl_sum.sh CHECKSUMS FILE   -> exit 0 when they agree, 1 (with a message) when not.
set -euo pipefail
want=$(awk -v f="$(basename "$2")" '$3 == f {print $1, $2}' "$1")
[ -n "$want" ] || { echo "$(basename "$2") is not listed in $1" >&2; exit 1; }
got=$(sum "$2" | awk '{print $1, $2}')
[ "$want" = "$got" ] || { echo "$(basename "$2"): checksum $got, Ensembl lists $want: the download is damaged" >&2; exit 1; }
