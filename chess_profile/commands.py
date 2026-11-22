"""Turns an issue title into a command.

Title formats (these are what the README links pre-fill):
    chess|move|e2e4|<game id>    play a move (UCI; promotions like e7e8q)
    chess|new|<finished game id> start the next game
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Union

_UCI = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")


class CommandError(ValueError):
    """The title isn't a chess command we understand."""


@dataclass(frozen=True)
class MoveCommand:
    uci: str
    game_id: int


@dataclass(frozen=True)
class NewGameCommand:
    finished_game_id: int


Command = Union[MoveCommand, NewGameCommand]


def parse_title(title: str) -> Command:
    parts = [p.strip() for p in title.strip().split("|")]
    if len(parts) < 2 or parts[0].lower() != "chess":
        raise CommandError("That issue title isn't a chess command.")
    action = parts[1].lower()
    if action == "move" and len(parts) == 4:
        uci = parts[2].lower()
        if not _UCI.match(uci):
            raise CommandError(f"`{parts[2]}` isn't a move I can read.")
        return MoveCommand(uci=uci, game_id=_game_id(parts[3]))
    if action == "new" and len(parts) == 3:
        return NewGameCommand(finished_game_id=_game_id(parts[2]))
    raise CommandError("That chess command is malformed. Please use the links on the README.")


def _game_id(text: str) -> int:
    if not text.isdigit():
        raise CommandError(f"`{text}` isn't a game number.")
    return int(text)
