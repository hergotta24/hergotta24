from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "update_token_stats.py"


def make_db(
    path: Path,
    started: float,
    values: tuple[int, int, int, int],
    session_id: str = "s1",
) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE sessions (
          id TEXT PRIMARY KEY, started_at REAL,
          input_tokens INTEGER, output_tokens INTEGER,
          cache_read_tokens INTEGER, cache_write_tokens INTEGER
        );
        CREATE TABLE session_model_usage (
          session_id TEXT, model TEXT,
          input_tokens INTEGER, output_tokens INTEGER,
          cache_read_tokens INTEGER, cache_write_tokens INTEGER
        );
        """
    )
    connection.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?)", (session_id, started, *values))
    connection.execute("INSERT INTO session_model_usage VALUES (?, 'model', ?, ?, ?, ?)", (session_id, *values))
    connection.commit()
    connection.close()


def run_generator(home: Path, repo: Path, state: Path, external: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--hermes-home",
            str(home),
            "--external-dir",
            str(external),
            "--repo",
            str(repo),
            "--state-dir",
            str(state),
            "--allow-no-external",
            "--now",
            "2026-11-20T12:00:00Z",
        ],
        text=True,
        capture_output=True,
    )


def test_generation_is_aggregate_and_privacy_safe(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    profile = home / "profiles" / "scout"
    profile.mkdir(parents=True)
    make_db(home / "state.db", 1794500000, (10, 20, 30, 40))
    make_db(profile / "state.db", 1795000000, (1, 2, 3, 4), "s2")
    repo = tmp_path / "repo"

    result = run_generator(home, repo, tmp_path / "state", tmp_path / "none")
    assert result.returncode == 0, result.stderr
    payload = json.loads((repo / "data" / "token-usage.json").read_text())
    assert payload["lifetime_tokens"] == 110
    assert payload["source_count"] == 2
    assert "default" not in json.dumps(payload).lower()
    assert "scout" not in json.dumps(payload).lower()
    svg = (repo / "assets" / "token-usage.svg").read_text()
    assert svg.startswith("<svg")
    root = ET.fromstring(svg)
    assert root.attrib["viewBox"] == "0 0 680 150"
    assert "<script" not in svg.lower()
    assert "foreignobject" not in svg.lower()
    assert not (repo / "data" / "token-history.json").exists()


def test_second_snapshot_uses_delta(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    home.mkdir()
    make_db(home / "state.db", 1794500000, (25, 25, 25, 25))
    repo = tmp_path / "repo"
    state = tmp_path / "state"
    state.mkdir()
    (state / "token-history.json").write_text('[{"date":"2026-11-13","total_tokens":40}]\n')

    result = run_generator(home, repo, state, tmp_path / "none")
    assert result.returncode == 0, result.stderr
    payload = json.loads((repo / "data" / "token-usage.json").read_text())
    assert payload["rolling_7d_tokens"] == 60
    assert payload["rolling_7d_method"] == "snapshot delta"


def test_duplicate_sessions_fail_closed(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    profile = home / "profiles" / "scout"
    profile.mkdir(parents=True)
    make_db(home / "state.db", 1794500000, (1, 1, 1, 1))
    make_db(profile / "state.db", 1795000000, (1, 1, 1, 1))

    result = run_generator(home, tmp_path / "repo", tmp_path / "state", tmp_path / "none")
    assert result.returncode != 0
    assert "Duplicate session IDs" in result.stderr


def test_counter_decrease_fails_closed(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    home.mkdir()
    make_db(home / "state.db", 1794500000, (1, 1, 1, 1))
    state = tmp_path / "state"
    state.mkdir()
    (state / "token-history.json").write_text('[{"date":"2026-11-19","total_tokens":100}]\n')

    result = run_generator(home, tmp_path / "repo", state, tmp_path / "none")
    assert result.returncode != 0
    assert "counter decreased" in result.stderr
