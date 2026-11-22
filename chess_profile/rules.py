"""Chess rules — a thin wrapper over python-chess so the rest of the code never touches it directly."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

import chess

from .state import BLACK, WHITE

PIECE_NAMES = {
    chess.KING: "King",
    chess.QUEEN: "Queen",
    chess.ROOK: "Rook",
    chess.BISHOP: "Bishop",
    chess.KNIGHT: "Knight",
    chess.PAWN: "Pawn",
}
_PIECE_ORDER = [chess.KING, chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN]


@dataclass(frozen=True)
class LegalMove:
    uci: str
    san: str
    piece: str  # "Knight", "Pawn", ...


@dataclass(frozen=True)
class GameResult:
    winner: Optional[str]  # WHITE, BLACK, or None for a draw
    reason: str  # "checkmate", "stalemate", "threefold repetition", ...


class ChessRules:
    def board_for(self, ucis: Iterable[str]) -> chess.Board:
        board = chess.Board()
        for uci in ucis:
            board.push_uci(uci)
        return board

    def legal_moves(self, board: chess.Board) -> List[LegalMove]:
        moves = []
        for move in board.legal_moves:
            piece = board.piece_type_at(move.from_square)
            moves.append((_PIECE_ORDER.index(piece), board.san(move), move.uci(), PIECE_NAMES[piece]))
        moves.sort()
        return [LegalMove(uci=uci, san=san, piece=name) for _, san, uci, name in moves]

    def play(self, board: chess.Board, uci: str) -> Optional[str]:
        """Plays the move on `board` and returns its SAN, or None if it isn't legal."""
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return None
        if move not in board.legal_moves:
            return None
        san = board.san(move)
        board.push(move)
        return san

    def parse_any(self, board: chess.Board, text: str) -> Optional[str]:
        """Accepts SAN ("Nf3") or UCI ("g1f3") and returns UCI, or None. Used by local play."""
        for parse in (board.parse_san, board.parse_uci):
            try:
                return parse(text.strip()).uci()
            except ValueError:
                continue
        return None

    def result(self, board: chess.Board) -> Optional[GameResult]:
        # Nobody is around to "claim" a draw in an async crowd game, so threefold repetition
        # and the fifty-move rule end the game automatically, but only once the repetition
        # has actually happened. (outcome(claim_draw=True) would end it a move early,
        # because it also counts a repetition the next move *could* make.)
        outcome = board.outcome()
        if outcome is None:
            if board.is_repetition(3):
                return GameResult(winner=None, reason="threefold repetition")
            if board.is_fifty_moves():
                return GameResult(winner=None, reason="fifty-move rule")
            return None
        winner = None if outcome.winner is None else (WHITE if outcome.winner else BLACK)
        return GameResult(winner=winner, reason=outcome.termination.name.lower().replace("_", " "))
