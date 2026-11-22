"""Builds the chess section of the README and swaps it in between the markers."""
from __future__ import annotations

from itertools import groupby
from pathlib import Path
from typing import List
from urllib.parse import quote, urlencode

from .config import ChessConfig
from .rules import LegalMove
from .state import ALEX, CROWD, ChessState, other_color

START_MARKER = "<!-- CHESS:START -->"
END_MARKER = "<!-- CHESS:END -->"
CREDIT = (
    "<sub>♟ Inspired by <a href=\"https://github.com/timburgan/timburgan\">Tim Burgan's community chess game</a> "
    "(<a href=\"https://github.com/timburgan\">@timburgan</a>). Thanks, Tim!</sub>"
)


class IssueLinks:
    """Links that open a new issue with the command pre-filled in the title."""

    def __init__(self, repo: str) -> None:
        self._repo = repo

    def move(self, uci: str, game_id: int) -> str:
        return self._new_issue(f"chess|move|{uci}|{game_id}", "Just press **Submit new issue**. A bot will play the move.")

    def new_game(self, finished_game_id: int) -> str:
        return self._new_issue(f"chess|new|{finished_game_id}", "Just press **Submit new issue** to start the next game.")

    def board(self) -> str:
        return f"https://github.com/{self._repo}#play-chess-against-me"

    def _new_issue(self, title: str, body: str) -> str:
        query = urlencode({"title": title, "body": body}, quote_via=quote)
        return f"https://github.com/{self._repo}/issues/new?{query}"


class ChessSectionBuilder:
    def __init__(self, config: ChessConfig, links: IssueLinks) -> None:
        self._config = config
        self._links = links

    def build(self, state: ChessState, legal_moves: List[LegalMove]) -> str:
        game = state.game
        name = self._config.owner_display_name
        lines = ["## Play chess against me", ""]
        if self._config.test_mode:
            lines += ["> 🧪 **Test mode:** the owner can play both sides and back-to-back moves are allowed.", ""]
        if state.board_image:
            lines += [f'<p align="center"><img src="{state.board_image}" width="420" alt="Current chess board, game {game.id}"></p>', ""]
        lines += [
            f"**Game {game.id}** · The crowd (you) plays **{game.crowd_color.title()}**, "
            f"{name} plays **{game.alex_color.title()}** · {len(game.moves)} moves played",
            "",
        ]
        if game.moves:
            last = game.moves[-1]
            who = f"@{last.user}" + (f" ({name})" if last.side == ALEX else "")
            lines += [f"Last move: **{last.san}** by {who} on {last.at[:10]}", ""]

        if not game.is_active:
            lines += self._finished(state)
        elif game.side_to_move == CROWD:
            lines += self._crowd_turn(state, legal_moves)
        else:
            lines += self._alex_turn(state, legal_moves)

        lines += self._how_it_works()
        lines += self._record_and_leaderboard(state)
        lines += [CREDIT]
        return "\n".join(lines)

    def _crowd_turn(self, state: ChessState, legal_moves: List[LegalMove]) -> List[str]:
        game = state.game
        lines = ["> **Your move!** Click a move below, then press **Submit new issue**. A bot plays it in about a minute."]
        if game.last_crowd_mover and not self._config.test_mode:
            lines.append(f"> @{game.last_crowd_mover} made the crowd's last move, so this one is up to someone else.")
        return lines + [""] + self._move_table(legal_moves, game.id)

    def _alex_turn(self, state: ChessState, legal_moves: List[LegalMove]) -> List[str]:
        game = state.game
        name = self._config.owner_display_name
        since = (game.last_move_at or game.started_at)[:10]
        return [
            f"> **Waiting on {name}** (since {since}). The crowd can move again once they reply. Check back soon!",
            "",
            f"<details><summary>{name}'s move links (only @{self._config.owner} can play these)</summary>",
            "",
            *self._move_table(legal_moves, game.id),
            "</details>",
            "",
        ]

    def _finished(self, state: ChessState) -> List[str]:
        game = state.game
        name = self._config.owner_display_name
        reason = game.result_reason or "game over"
        headline = {
            ALEX: f"**Game {game.id} is over. {name} wins by {reason}.**",
            CROWD: f"**Game {game.id} is over. The crowd wins by {reason}! 🎉**",
        }.get(game.result, f"**Game {game.id} is over. It's a draw by {reason}.**")
        next_color = other_color(game.alex_color).title()
        return [
            f"> {headline}",
            f"> [**Start game {game.id + 1}**]({self._links.new_game(game.id)}). {name} will play {next_color}.",
            "",
        ]

    def _move_table(self, legal_moves: List[LegalMove], game_id: int) -> List[str]:
        rows = ["| Piece | Moves |", "| :-- | :-- |"]
        for piece, moves in groupby(legal_moves, key=lambda m: m.piece):
            links = " ".join(f"[{m.san}]({self._links.move(m.uci, game_id)})" for m in moves)
            rows.append(f"| {piece} | {links} |")
        return rows + [""]

    def _how_it_works(self) -> List[str]:
        name = self._config.owner_display_name
        return [
            "<details><summary>How it works</summary>",
            "",
            f"Everyone visiting this page plays together as one side against {name}. "
            "Each move link opens a new issue with the move already filled in. Submitting it "
            "starts a GitHub Action that checks the move, updates the board image, and rewrites this README. "
            f"The first legal move wins. Nobody can make two crowd moves in a row. {name} gets pinged on "
            "every turn and plays from this same page.",
            "",
            "</details>",
            "",
        ]

    def _record_and_leaderboard(self, state: ChessState) -> List[str]:
        r = state.record
        name = self._config.owner_display_name
        lines = [f"**{name} vs the crowd:** {r.wins} W · {r.losses} L · {r.draws} D", ""]
        top = sorted(state.crowd_moves.items(), key=lambda kv: (-kv[1], kv[0].lower()))
        top = top[: self._config.leaderboard_size]
        if not top:
            return lines + ["_No crowd moves yet. Be the first!_", ""]
        lines += ["**Top crowd players**", "", "| # | Player | Moves |", "| --: | :-- | --: |"]
        lines += [f"| {i} | @{user} | {count} |" for i, (user, count) in enumerate(top, start=1)]
        return lines + [""]


def replace_section(text: str, section: str) -> str:
    start = text.find(START_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"README needs {START_MARKER} and {END_MARKER} markers.")
    return text[: start + len(START_MARKER)] + "\n" + section + "\n" + text[end:]


class ReadmeUpdater:
    def __init__(self, path: Path, builder: ChessSectionBuilder) -> None:
        self._path = path
        self._builder = builder

    def update(self, state: ChessState, legal_moves: List[LegalMove]) -> None:
        text = self._path.read_text(encoding="utf-8")
        self._path.write_text(replace_section(text, self._builder.build(state, legal_moves)), encoding="utf-8")
