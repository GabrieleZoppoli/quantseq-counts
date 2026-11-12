#!/usr/bin/env bash
# Installs quantseq-counts into one folder, without administrator rights:
#   bash install.sh --prefix /path/to/quantseq-counts
# It copies the package there, downloads micromamba 2.9.0 and Nextflow 25.04.8 (checked against the sha256 values
# of conda/downloads.tsv), and builds the environment from the lock file of this machine's platform. Everything,
# including the package cache, stays inside the prefix. Afterwards: /path/to/quantseq-counts/bin/quantseq-counts
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX=""; FORCE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --prefix) PREFIX="${2:-}"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
[ -n "$PREFIX" ] || { echo "usage: bash install.sh --prefix FOLDER" >&2; exit 2; }
case "$(uname -s)-$(uname -m)" in
  Linux-x86_64) PLAT=linux-64 ;;
  Darwin-arm64) PLAT=osx-arm64 ;;
  *) echo "unsupported platform $(uname -s) $(uname -m): linux x86_64 and macOS arm64 are supported" >&2; exit 2 ;;
esac
VERSION=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$SRC/src/quantseq_counts/__init__.py")
if [ -e "$PREFIX/VERSION" ] && [ $FORCE -eq 0 ]; then
  echo "$PREFIX already holds quantseq-counts $(cat "$PREFIX/VERSION"); use another folder, or --force to replace it" >&2; exit 2
fi
mkdir -p "$PREFIX/libexec" "$PREFIX/bin"
PREFIX="$(cd "$PREFIX" && pwd)"

sha() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -c1-64; else shasum -a 256 "$1" | cut -c1-64; fi; }
fetch() {  # name platform destination
  local row url want
  row=$(awk -F'\t' -v n="$1" -v p="$2" '$1 == n && ($2 == p || $2 == "any")' "$SRC/conda/downloads.tsv")
  url=$(printf '%s' "$row" | cut -f3); want=$(printf '%s' "$row" | cut -f4)
  [ -n "$url" ] || { echo "no download for $1 on $2" >&2; exit 1; }
  echo "downloading $1 ($url)"
  curl -fsSL --retry 3 -o "$3.part" "$url"
  [ "$(sha "$3.part")" = "$want" ] || { echo "checksum of $1 differs from conda/downloads.tsv: not installed" >&2; rm -f "$3.part"; exit 1; }
  mv "$3.part" "$3"; chmod 755 "$3"
}

echo "copying quantseq-counts $VERSION to $PREFIX"
items=""; for i in bin src schema conda tests workflow docs tools LICENSE README.md CITATION.cff install.sh; do [ -e "$SRC/$i" ] && items="$items $i"; done
( cd "$SRC" && tar cf - --exclude=.git --exclude=.superpowers --exclude=__pycache__ --exclude=.pytest_cache $items ) | ( cd "$PREFIX" && tar xf - )

fetch micromamba "$PLAT" "$PREFIX/libexec/micromamba"
echo "building the environment from conda/conda-$PLAT.lock"
MAMBA_ROOT_PREFIX="$PREFIX/mamba" "$PREFIX/libexec/micromamba" create -y -q -p "$PREFIX/env" -f "$SRC/conda/conda-$PLAT.lock"

fetch nextflow any "$PREFIX/libexec/nextflow-25.04.8-dist"
cat > "$PREFIX/bin/nextflow" <<WRAP
#!/usr/bin/env bash
# Nextflow 25.04.8 with the Java of this installation.
export JAVA_HOME="$PREFIX/env/lib/jvm" PATH="$PREFIX/env/lib/jvm/bin:$PREFIX/env/bin:\$PATH" NXF_HOME="\${NXF_HOME:-$PREFIX/nxf}"
exec "$PREFIX/libexec/nextflow-25.04.8-dist" "\$@"
WRAP
chmod 755 "$PREFIX/bin/nextflow"
printf '%s\n' "$VERSION" > "$PREFIX/VERSION"
echo "installed quantseq-counts $VERSION in $PREFIX"
echo "try: $PREFIX/bin/quantseq-counts --version"
