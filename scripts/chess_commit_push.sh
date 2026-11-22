#!/usr/bin/env bash
# Commits the chess bot's changes and pushes, retrying if another push landed first
# (e.g. the nightly token-widget update). Used by both chess workflows.
set -euo pipefail

message=${1:?commit message required}
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -A README.md data/chess assets/chess
if git diff --cached --quiet; then
  echo "Nothing to commit."
  exit 0
fi
git commit -m "$message"
for attempt in 1 2 3; do
  if git push origin "HEAD:${GITHUB_REF_NAME:-main}"; then
    exit 0
  fi
  echo "Push rejected (attempt $attempt); rebasing on the latest main."
  git pull --rebase origin "${GITHUB_REF_NAME:-main}"
done
echo "Could not push after 3 attempts." >&2
exit 1
