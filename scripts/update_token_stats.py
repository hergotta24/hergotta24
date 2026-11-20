#!/usr/bin/env python3
"""Generate privacy-safe aggregate AI token statistics for the profile README."""

from __future__ import annotations

import argparse
import html
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TOKEN_COLUMNS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")
LOCAL_TZ = ZoneInfo("America/Chicago")


@dataclass(frozen=True)
class Usage:
    total: int
    recent_estimate: int
    tracking_since: datetime | None
    fresh: bool = True


def _sum_expr(alias: str = "") -> str:
    prefix = f"{alias}." if alias else ""
    return " + ".join(f"COALESCE({prefix}{column}, 0)" for column in TOKEN_COLUMNS)


def read_hermes_db(path: Path, cutoff: float) -> Usage:
    """Read a Hermes state database without changing it.

    Per-model rows include auxiliary calls. Sessions without those rows use the
    session aggregate as a compatibility fallback.
    """
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only = ON")
        has_usage = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='session_model_usage'"
        ).fetchone()
        if has_usage:
            total = connection.execute(
                f"SELECT COALESCE(SUM({_sum_expr('u')}), 0) "
                "FROM session_model_usage u"
            ).fetchone()[0]
            total += connection.execute(
                f"SELECT COALESCE(SUM({_sum_expr('s')}), 0) FROM sessions s "
                "WHERE NOT EXISTS (SELECT 1 FROM session_model_usage u WHERE u.session_id = s.id)"
            ).fetchone()[0]
            recent = connection.execute(
                f"SELECT COALESCE(SUM({_sum_expr('u')}), 0) "
                "FROM session_model_usage u JOIN sessions s ON s.id = u.session_id "
                "WHERE s.started_at >= ?",
                (cutoff,),
            ).fetchone()[0]
            recent += connection.execute(
                f"SELECT COALESCE(SUM({_sum_expr('s')}), 0) FROM sessions s "
                "WHERE s.started_at >= ? AND NOT EXISTS "
                "(SELECT 1 FROM session_model_usage u WHERE u.session_id = s.id)",
                (cutoff,),
            ).fetchone()[0]
        else:
            total = connection.execute(
                f"SELECT COALESCE(SUM({_sum_expr()}), 0) FROM sessions"
            ).fetchone()[0]
            recent = connection.execute(
                f"SELECT COALESCE(SUM({_sum_expr()}), 0) FROM sessions WHERE started_at >= ?",
                (cutoff,),
            ).fetchone()[0]
        started = connection.execute("SELECT MIN(started_at) FROM sessions").fetchone()[0]
        tracking_since = datetime.fromtimestamp(started, timezone.utc) if started else None
        return Usage(int(total), int(recent), tracking_since)
    finally:
        connection.close()


def discover_hermes_databases(home: Path) -> list[Path]:
    candidates = [home / "state.db", *(home / "profiles").glob("*/state.db")]
    return sorted(path for path in candidates if path.is_file())


def ensure_unique_sessions(paths: list[Path]) -> None:
    seen: set[str] = set()
    for path in paths:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            connection.execute("PRAGMA query_only = ON")
            for (session_id,) in connection.execute("SELECT id FROM sessions"):
                if session_id in seen:
                    raise SystemExit("Duplicate session IDs across Hermes sources; refusing to publish")
                seen.add(session_id)
        finally:
            connection.close()


def read_external_sources(directory: Path, now: datetime) -> list[Usage]:
    usages: list[Usage] = []
    if not directory.is_dir():
        return usages
    for path in sorted(directory.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        observed = datetime.fromisoformat(payload["observed_at"].replace("Z", "+00:00"))
        tracking = datetime.fromisoformat(payload["tracking_since"].replace("Z", "+00:00"))
        usages.append(
            Usage(
                total=int(payload["total_tokens"]),
                recent_estimate=int(payload.get("rolling_7d_tokens", 0)),
                tracking_since=tracking,
                fresh=(now.astimezone(timezone.utc) - observed.astimezone(timezone.utc)) <= timedelta(hours=36),
            )
        )
    return usages


def format_tokens(value: int) -> str:
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def render_svg(total: int, rolling: int, tracking_label: str, method: str) -> str:
    total_text = html.escape(format_tokens(total))
    rolling_text = html.escape(format_tokens(rolling))
    subtitle = html.escape(f"Tracking since {tracking_label} · {method}")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="680" height="150" viewBox="0 0 680 150" role="img" aria-labelledby="title desc">
  <title id="title">Aggregate AI token usage</title>
  <desc id="desc">{total_text} tokens tracked since {html.escape(tracking_label)}; {rolling_text} in the last seven days.</desc>
  <style>
    .bg {{ fill: #0d1117; stroke: #30363d; }}
    .label {{ fill: #8b949e; font: 600 13px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; letter-spacing: .04em; }}
    .value {{ fill: #f0f6fc; font: 700 30px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    .title {{ fill: #58a6ff; font: 700 16px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    .note {{ fill: #8b949e; font: 12px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    .rule {{ stroke: #30363d; }}
  </style>
  <rect class="bg" x="0.5" y="0.5" width="679" height="149" rx="10"/>
  <text class="title" x="24" y="30">AGGREGATE AI TOKEN USAGE</text>
  <line class="rule" x1="340" y1="48" x2="340" y2="112"/>
  <text class="label" x="24" y="65">LIFETIME</text>
  <text class="value" x="24" y="101">{total_text}</text>
  <text class="label" x="372" y="65">LAST 7 DAYS</text>
  <text class="value" x="372" y="101">{rolling_text}</text>
  <text class="note" x="24" y="132">{subtitle}</text>
</svg>
'''


def load_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def calculate_rolling(history: list[dict], today: str, total: int, estimate: int) -> tuple[int, str]:
    target = datetime.fromisoformat(today).date() - timedelta(days=7)
    eligible = [row for row in history if datetime.fromisoformat(row["date"]).date() <= target]
    if eligible:
        baseline = max(eligible, key=lambda row: row["date"])
        return max(0, total - int(baseline["total_tokens"])), "snapshot delta"
    return estimate, "session-start estimate until 7 daily snapshots exist"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-home", type=Path, default=Path.home() / ".hermes")
    parser.add_argument("--external-dir", type=Path, default=Path.home() / ".hermes" / "token-usage-sources")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--state-dir", type=Path, default=Path.home() / ".hermes" / "token-widget-state")
    parser.add_argument("--allow-no-external", action="store_true", help="Testing only")
    parser.add_argument("--now", help="ISO timestamp used by tests")
    args = parser.parse_args()

    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=7)).timestamp()
    databases = discover_hermes_databases(args.hermes_home)
    ensure_unique_sessions(databases)
    usages = [read_hermes_db(path, cutoff) for path in databases]
    if not args.allow_no_external and not (args.external_dir / "claude-code.json").is_file():
        raise SystemExit("Required Claude Code aggregate is missing; refusing to publish")
    usages.extend(read_external_sources(args.external_dir, now))
    if not usages:
        raise SystemExit("No trustworthy token sources found")
    if any(not item.fresh for item in usages):
        raise SystemExit("A required token source is stale; refusing to publish")

    total = sum(item.total for item in usages)
    estimate = sum(item.recent_estimate for item in usages)
    started = min(item.tracking_since for item in usages if item.tracking_since is not None)
    local_now = now.astimezone(LOCAL_TZ)
    today = local_now.date().isoformat()

    data_dir = args.repo / "data"
    assets_dir = args.repo / "assets"
    data_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    args.state_dir.mkdir(parents=True, exist_ok=True)
    history_path = args.state_dir / "token-history.json"
    history = [row for row in load_history(history_path) if row.get("date") != today]
    if history and total < int(max(history, key=lambda row: row["date"])["total_tokens"]):
        raise SystemExit("Aggregate counter decreased; refusing to publish")
    rolling, method = calculate_rolling(history, today, total, estimate)
    history.append({"date": today, "total_tokens": total})
    history.sort(key=lambda row: row["date"])

    tracking_label = started.astimezone(LOCAL_TZ).date().isoformat()
    generated = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    public = {
        "generated_at": generated,
        "lifetime_tokens": total,
        "rolling_7d_tokens": rolling,
        "rolling_7d_method": method,
        "tracking_since": tracking_label,
        "source_count": len(usages),
        "stale_source_count": 0,
        "definition": "Input + output + cache-read + cache-write tokens from available agent records",
    }
    (data_dir / "token-usage.json").write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
    history_path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    (assets_dir / "token-usage.svg").write_text(
        render_svg(total, rolling, tracking_label, method), encoding="utf-8"
    )
    print(json.dumps(public))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
