# Token widget methodology

The profile widget is a privacy-safe summary of aggregate AI-agent token activity. It is designed to be reproducible without publishing conversation content or account metadata.

## Published fields

- Lifetime aggregate tokens
- Rolling seven-day aggregate tokens
- Tracking start date
- Generation time and calculation method in `data/token-usage.json`

A token is counted when a trustworthy source records it as an input, output, cache-read, or cache-write token. Reasoning tokens are not added separately because providers may already include them in output accounting.

The public output does **not** contain prompts, costs, credentials, account identifiers, model names, or per-agent totals.

## Sources and coverage

`scripts/update_token_stats.py` reads every available Hermes profile database on the Raspberry Pi in SQLite read-only mode. It can also ingest cumulative external-agent records from `~/.hermes/token-usage-sources/*.json` once a trustworthy collector is connected.

An external record must use this shape:

```json
{
  "observed_at": "2026-11-20T23:55:00Z",
  "tracking_since": "2026-11-20T00:00:00Z",
  "total_tokens": 123456,
  "rolling_7d_tokens": 123456
}
```

The public data reports only the number of sources and whether any source is stale. An external source older than 36 hours is marked stale rather than silently treated as current.

## Seven-day calculation

For the first seven daily runs, the widget uses a disclosed session-start estimate: it sums usage for sessions whose recorded start time is within the last seven days. This can undercount long-running older sessions or count all usage from a recently started long session.

Snapshots are stored privately under `~/.hermes/token-widget-state/`, not committed. After a snapshot at least seven days old exists, the widget subtracts that cumulative snapshot from the current cumulative total. This produces an idempotent rolling window and avoids double-counting repeated runs on the same day.

## Nightly publisher

`scripts/nightly-token-update.sh`:

1. Fetches `origin/main`.
2. Exits successfully while the feature is awaiting merge.
3. Refuses to run on a dirty working tree and updates `main` by fast-forward only.
4. Generates aggregate data and the SVG.
5. Commits only generated token artifacts when totals changed.
6. Pushes with the clearly identified `hergotta24-token-bot` Git identity.

The publisher requires only repository write access. It does not place GitHub credentials in the repository.

## Local verification

```bash
uv run --with pytest pytest -q tests
python3 scripts/update_token_stats.py
python3 -m json.tool data/token-usage.json
python3 -m json.tool data/token-history.json
```
