from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from chess_profile.cli import build_service
from chess_profile.config import load_config
from chess_profile.rules import ChessRules
from chess_profile.state import ALEX, BLACK, JsonStateStore

OWNER = "hergotta24"
README = "# Hi\n\n<!-- CHESS:START -->\n<!-- CHESS:END -->\n\n## Also building\n"


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


class Harness:
    """A throwaway repo folder wired to the real GameService, with helpers for playing games."""

    def __init__(self, root: Path, test_mode: bool = False) -> None:
        (root / "chess.config.json").write_text(
            json.dumps({"owner": OWNER, "test_mode": test_mode, "reminder_days": 3, "leaderboard_size": 5}),
            encoding="utf-8",
        )
        (root / "README.md").write_text(README, encoding="utf-8")
        self.root = root
        self.clock = FakeClock()
        self.config = load_config(root, env={"GITHUB_REPOSITORY": f"{OWNER}/{OWNER}"})
        self.service = build_service(root, self.config, clock=self.clock)
        self.store = JsonStateStore(root / "data" / "chess" / "state.json")
        self.rules = ChessRules()
        self.issue = 0
        self._crowd = ["alice", "bob"]
        self.service.reset(BLACK)

    @property
    def state(self):
        return self.store.load()

    @property
    def readme(self) -> str:
        return (self.root / "README.md").read_text(encoding="utf-8")

    def move(self, san: str, user: str = None):
        """Plays a SAN move as `user`, or as whoever's turn it is (crowd users alternate)."""
        game = self.state.game
        board = self.rules.board_for(m.uci for m in game.moves)
        uci = self.rules.parse_any(board, san) or san
        if user is None:
            user = OWNER if game.side_to_move == ALEX else next(u for u in self._crowd if u != game.last_crowd_mover)
        return self.raw(f"chess|move|{uci}|{game.id}", user)

    def play(self, *sans: str):
        reply = None
        for san in sans:
            reply = self.move(san)
            assert reply.accepted, f"{san} rejected: {reply.body}"
        return reply

    def raw(self, title: str, user: str):
        self.issue += 1
        return self.service.handle_issue(title, user, self.issue)


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


@pytest.fixture
def test_mode_harness(tmp_path: Path) -> Harness:
    return Harness(tmp_path, test_mode=True)
