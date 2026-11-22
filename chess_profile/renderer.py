"""Draws the board as an SVG and manages the image files in the repo."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

import chess
import chess.svg

from .state import WHITE

BOARD_COLORS = {
    "square light": "#e6e9f0",
    "square dark": "#7d8fb3",
    "square light lastmove": "#f3d98b",
    "square dark lastmove": "#d1ae5a",
    "margin": "#2b3240",
    "coord": "#e6e9f0",
}


class BoardRenderer(Protocol):
    def render(self, board: chess.Board, orientation: str) -> str: ...


class SvgBoardRenderer:
    def __init__(self, size: int = 420) -> None:
        self._size = size

    def render(self, board: chess.Board, orientation: str) -> str:
        last_move = board.peek() if board.move_stack else None
        check = board.king(board.turn) if board.is_check() else None
        return chess.svg.board(
            board,
            orientation=chess.WHITE if orientation == WHITE else chess.BLACK,
            lastmove=last_move,
            check=check,
            size=self._size,
            colors=BOARD_COLORS,
        )


class BoardImageStore:
    """Writes one file per position (board-<game>-<ply>.svg) and deletes the old ones.

    A new filename every move sidesteps GitHub's image proxy cache, which would
    otherwise keep showing a stale board.
    """

    def __init__(self, root: Path, images_dir: Path) -> None:
        self._root = root
        self._dir = images_dir

    def write(self, game_id: int, ply: int, svg: str) -> str:
        self._dir.mkdir(parents=True, exist_ok=True)
        name = f"board-{game_id}-{ply}.svg"
        for old in self._dir.glob("board-*.svg"):
            if old.name != name:
                old.unlink()
        (self._dir / name).write_text(svg, encoding="utf-8")
        return (self._dir / name).relative_to(self._root).as_posix()
