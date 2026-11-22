"""Who is allowed to move right now. Kept separate from chess rules so turn
rules (e.g. a future voting window) can change without touching anything else."""
from __future__ import annotations

from typing import Optional, Protocol

from .config import ChessConfig
from .state import ALEX, Game


class TurnPolicy(Protocol):
    def rejection(self, game: Game, user: str) -> Optional[str]:
        """Returns why `user` may not move now, or None if they may."""
        ...


class AlexVsCrowdPolicy:
    """Alex's turn: only Alex. Crowd's turn: anyone but Alex, and not the previous crowd mover."""

    def __init__(self, config: ChessConfig) -> None:
        self._owner = config.owner.lower()
        self._name = config.owner_display_name
        self._test_mode = config.test_mode

    def rejection(self, game: Game, user: str) -> Optional[str]:
        is_owner = user.lower() == self._owner
        if game.side_to_move == ALEX:
            if is_owner:
                return None
            return f"It's {self._name}'s turn right now. Check back once they've replied!"
        if self._test_mode:
            return None
        if is_owner:
            return f"It's the crowd's turn, {self._name} can't move for the crowd."
        last = game.last_crowd_mover
        if last and user.lower() == last.lower():
            return "You made the crowd's last move. Someone else has to make this one (no back-to-back moves)."
        return None
