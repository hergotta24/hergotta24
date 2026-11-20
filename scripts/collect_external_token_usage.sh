#!/usr/bin/env bash
set -euo pipefail

output_dir=${TOKEN_SOURCE_DIR:-/home/ahergott/.hermes/token-usage-sources}
collector='C:\Users\hergo\.hermes-tools\collect-claude-usage.ps1'
mkdir -p "$output_dir"
tmp=$(mktemp "$output_dir/claude-code.json.XXXXXX")
trap 'rm -f "$tmp"' EXIT

if ! hc exec --on laptop powershell -NoProfile -File "$collector" >"$tmp"; then
  echo "Claude Code collector unavailable; retaining the prior snapshot." >&2
  exit 0
fi

python3 - "$tmp" <<'PY'
import json, sys
from pathlib import Path
payload=json.loads(Path(sys.argv[1]).read_text())
required=("observed_at","tracking_since","total_tokens","rolling_7d_tokens")
if any(key not in payload for key in required):
    raise SystemExit("collector output is missing required fields")
if any(int(payload[key]) < 0 for key in ("total_tokens","rolling_7d_tokens")):
    raise SystemExit("collector returned a negative token count")
PY
mv "$tmp" "$output_dir/claude-code.json"
trap - EXIT
