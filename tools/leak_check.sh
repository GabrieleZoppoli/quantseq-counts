#!/usr/bin/env bash
# Searches a directory (and, with --history, every commit, commit message and author line of its git repository)
# for the patterns of a file kept outside the repository: one extended regular expression per line.
# Usage: tools/leak_check.sh --patterns FILE [--history] DIR
# Prints one line per hit (file:line:pattern, or commit:file:line:pattern, or commit:message:pattern) and exits
# 0 when nothing is found, 1 when something is, 2 on a usage error. Run it before every push.
set -uo pipefail
PAT=""; HIST=0; DIR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --patterns) PAT="${2:-}"; shift 2 ;;
    --history) HIST=1; shift ;;
    -*) echo "unknown option $1" >&2; exit 2 ;;
    *) DIR="$1"; shift ;;
  esac
done
[ -n "$PAT" ] && [ -f "$PAT" ] || { echo "usage: leak_check.sh --patterns FILE [--history] DIR (pattern file missing)" >&2; exit 2; }
[ -n "$DIR" ] && [ -d "$DIR" ] || { echo "usage: leak_check.sh --patterns FILE [--history] DIR (directory missing)" >&2; exit 2; }
cd "$DIR" || exit 2
hits=0
while IFS= read -r p || [ -n "$p" ]; do
  [ -z "$p" ] && continue
  case "$p" in \#*) continue ;; esac
  # working tree, tracked or not, hidden files included, .git excluded
  while IFS= read -r h; do echo "${h#./}:$p"; hits=1; done < <(grep -rEnIo --exclude-dir=.git -e "$p" . 2>/dev/null | cut -d: -f1,2)
  if [ $HIST -eq 1 ] && git rev-parse --git-dir >/dev/null 2>&1 && git rev-parse HEAD >/dev/null 2>&1; then
    while IFS= read -r c; do
      while IFS= read -r h; do echo "$h:$p"; hits=1; done < <(git grep -EnIo -e "$p" "$c" 2>/dev/null | cut -d: -f1-3)
      if git log -1 --format='%B%n%an%n%ae%n%cn%n%ce' "$c" | grep -Eq -e "$p"; then echo "$c:message:$p"; hits=1; fi
    done < <(git rev-list --all)
  fi
done < "$PAT"
exit $hits
