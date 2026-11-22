"""Settings and file locations. Everything environment-specific lives here."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

CONFIG_FILE = "chess.config.json"


@dataclass(frozen=True)
class ChessConfig:
    owner: str
    """GitHub login of the person the crowd plays against."""
    repo: str
    """"owner/name" of the repo the move links point at."""
    owner_display_name: str = "Alex"
    test_mode: bool = False
    """Owner may move for the crowd and the no-back-to-back rule is off. Sandbox only."""
    reminder_days: int = 3
    leaderboard_size: int = 5


def load_config(root: Path, env: Mapping[str, str] = os.environ) -> ChessConfig:
    """Read chess.config.json, letting the environment override per-repo values.

    GITHUB_REPOSITORY (set by Actions) picks the repo, so the same code works in the
    profile repo and the private sandbox. CHESS_TEST_MODE=true (a repo variable in the
    sandbox) turns on test mode without changing any committed file.
    """
    raw = json.loads((root / CONFIG_FILE).read_text(encoding="utf-8"))
    owner = raw["owner"]
    test_mode_env = env.get("CHESS_TEST_MODE", "").strip().lower()
    return ChessConfig(
        owner=owner,
        repo=env.get("GITHUB_REPOSITORY") or raw.get("repo") or f"{owner}/{owner}",
        owner_display_name=raw.get("owner_display_name", "Alex"),
        test_mode=test_mode_env == "true" if test_mode_env else bool(raw.get("test_mode", False)),
        reminder_days=int(raw.get("reminder_days", 3)),
        leaderboard_size=int(raw.get("leaderboard_size", 5)),
    )


@dataclass(frozen=True)
class RepoPaths:
    root: Path

    @property
    def state_file(self) -> Path:
        return self.root / "data" / "chess" / "state.json"

    @property
    def images_dir(self) -> Path:
        return self.root / "assets" / "chess"

    @property
    def readme(self) -> Path:
        return self.root / "README.md"
