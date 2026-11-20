#!/usr/bin/env bash
set -euo pipefail

repo=${PROFILE_REPO_DIR:-/home/ahergott/projects/github-portfolio/hergotta24}
cd "$repo"

git fetch origin main
if ! git show origin/main:scripts/update_token_stats.py >/dev/null 2>&1; then
  echo "Token widget is awaiting merge to main; nothing to update."
  exit 0
fi

git switch main
if [ -n "$(git status --porcelain)" ]; then
  echo "Profile publisher working tree is dirty; refusing to publish." >&2
  exit 1
fi
git pull --ff-only origin main
scripts/collect_external_token_usage.sh
python3 scripts/update_token_stats.py

if git diff --quiet -- assets/token-usage.svg data/token-usage.json; then
  echo "Token totals are unchanged."
  exit 0
fi

git config user.name "hergotta24-token-bot"
git config user.email "hergotta24-token-bot@users.noreply.github.com"
git add assets/token-usage.svg data/token-usage.json
git commit -m "chore: update nightly token usage"
git push origin main
