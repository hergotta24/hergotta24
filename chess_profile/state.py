"""The saved game: what it holds and how it is stored."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Protocol

ALEX = "alex"
CROWD = "crowd"
WHITE = "white"
BLACK = "black"


def other_color(color: str) -> str:
    return BLACK if color == WHITE else WHITE


@dataclass
class MoveRecord:
    uci: str
    san: str
    user: str
    side: str  # ALEX or CROWD
    at: str  # ISO-8601 UTC


@dataclass
class Game:
    id: int
    alex_color: str
    started_at: str
    moves: List[MoveRecord] = field(default_factory=list)
    status: str = "active"  # "active" | "finished"
    result: Optional[str] = None  # ALEX | CROWD | "draw"
    result_reason: Optional[str] = None
    last_move_at: Optional[str] = None
    last_crowd_mover: Optional[str] = None
    last_reminder_at: Optional[str] = None

    @property
    def crowd_color(self) -> str:
        return other_color(self.alex_color)

    @property
    def color_to_move(self) -> str:
        return WHITE if len(self.moves) % 2 == 0 else BLACK

    @property
    def side_to_move(self) -> str:
        return ALEX if self.color_to_move == self.alex_color else CROWD

    @property
    def is_active(self) -> bool:
        return self.status == "active"


@dataclass
class Record:
    """Alex's results against the crowd."""

    wins: int = 0
    losses: int = 0
    draws: int = 0


@dataclass
class ChessState:
    game: Game
    record: Record = field(default_factory=Record)
    crowd_moves: Dict[str, int] = field(default_factory=dict)
    reminder_issue: Optional[int] = None
    board_image: Optional[str] = None  # repo-relative path of the current board SVG

    @staticmethod
    def fresh(alex_color: str, now: str) -> "ChessState":
        return ChessState(game=Game(id=1, alex_color=alex_color, started_at=now))

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "ChessState":
        game = dict(data["game"])
        game["moves"] = [MoveRecord(**m) for m in game.get("moves", [])]
        return ChessState(
            game=Game(**game),
            record=Record(**data.get("record", {})),
            crowd_moves=dict(data.get("crowd_moves", {})),
            reminder_issue=data.get("reminder_issue"),
            board_image=data.get("board_image"),
        )


class StateStore(Protocol):
    def load(self) -> ChessState: ...

    def save(self, state: ChessState) -> None: ...


class JsonStateStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> ChessState:
        return ChessState.from_dict(json.loads(self._path.read_text(encoding="utf-8")))

    def save(self, state: ChessState) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(state.to_dict(), indent=2) + "\n", encoding="utf-8")
