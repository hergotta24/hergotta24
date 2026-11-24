"""Draws the board and manages the image files in the repo.

The README embeds a PNG, not an SVG. GitHub serves README images from
raw.githubusercontent.com, and some corporate browsers, proxies and security
policies block `image/svg+xml` there because SVG can carry active content.
A plain raster image shows up everywhere an ordinary photo would.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Protocol

import chess
import chess.svg
import resvg_py
from PIL import Image

from .state import WHITE

BOARD_COLORS = {
    "square light": "#e6e9f0",
    "square dark": "#7d8fb3",
    "square light lastmove": "#f3d98b",
    "square dark lastmove": "#d1ae5a",
    "margin": "#2b3240",
    "coord": "#e6e9f0",
}
DISPLAY_SIZE = 420  # CSS pixels in the README; the PNG is drawn at 2x so it stays sharp on HiDPI screens
PNG_COLORS = 64  # palette size; keeps each board ~30 KB so the repo doesn't balloon one move at a time


class BoardRenderer(Protocol):
    extension: str

    def render(self, board: chess.Board, orientation: str) -> bytes: ...


class SvgBoardRenderer:
    extension = "svg"

    def __init__(self, size: int = DISPLAY_SIZE) -> None:
        self._size = size

    def svg(self, board: chess.Board, orientation: str) -> str:
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

    def render(self, board: chess.Board, orientation: str) -> bytes:
        return self.svg(board, orientation).encode("utf-8")


class PngBoardRenderer:
    """Rasterizes the SVG board with resvg. The board has no text, so no fonts are needed."""

    extension = "png"

    def __init__(self, pixels: int = DISPLAY_SIZE * 2) -> None:
        self._pixels = pixels
        self._svg = SvgBoardRenderer()

    def render(self, board: chess.Board, orientation: str) -> bytes:
        raw = resvg_py.svg_to_bytes(
            svg_string=self._svg.svg(board, orientation),
            width=self._pixels,
            height=self._pixels,
            skip_system_fonts=True,
        )
        image = Image.open(io.BytesIO(bytes(raw))).convert("RGB").quantize(PNG_COLORS)
        out = io.BytesIO()
        image.save(out, format="PNG", optimize=True)
        return out.getvalue()


class BoardImageStore:
    """Writes one file per position (board-<game>-<ply>.<ext>) and deletes the old ones.

    A new filename every move sidesteps GitHub's image proxy cache, which would
    otherwise keep showing a stale board. Old boards of any format are removed,
    so switching formats leaves no orphaned files behind.
    """

    def __init__(self, root: Path, images_dir: Path) -> None:
        self._root = root
        self._dir = images_dir

    def write(self, game_id: int, ply: int, image: bytes, extension: str) -> str:
        self._dir.mkdir(parents=True, exist_ok=True)
        name = f"board-{game_id}-{ply}.{extension}"
        for old in self._dir.glob("board-*.*"):
            if old.name != name:
                old.unlink()
        (self._dir / name).write_bytes(image)
        return (self._dir / name).relative_to(self._root).as_posix()
