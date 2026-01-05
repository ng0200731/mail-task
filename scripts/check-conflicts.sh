#!/usr/bin/env bash
# scripts/check-conflicts.sh
# Fail the commit if any file about to be committed still contains Git merge
# conflict markers ("<<<<<<<", "=======", ">>>>>>>").

set -euo pipefail

# Get list of staged files (those to be committed)
staged=$(git diff --cached --name-only --diff-filter=ACM)

if [[ -z "$staged" ]]; then
  exit 0  # nothing to check
fi

fail=false
for f in $staged; do
  if [[ ! -f "$f" ]]; then
    continue
  fi
  if grep -En "^(<<<<<<<|=======|>>>>>>>)" "$f" >/dev/null; then
    echo "ERROR: merge-conflict markers found in staged file $f" >&2
    fail=true
  fi
done

if [[ "$fail" = true ]]; then
  echo "\nCommit aborted. Please resolve conflicts and remove markers." >&2
  exit 1
fi

exit 0


