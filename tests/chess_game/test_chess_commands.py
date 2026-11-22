import pytest

from chess_profile.commands import CommandError, MoveCommand, NewGameCommand, parse_title


def test_parses_move():
    assert parse_title("chess|move|e2e4|3") == MoveCommand(uci="e2e4", game_id=3)


def test_parses_promotion_and_ignores_case_and_spaces():
    assert parse_title(" Chess|MOVE|E7E8Q|1 ") == MoveCommand(uci="e7e8q", game_id=1)


def test_parses_new_game():
    assert parse_title("chess|new|4") == NewGameCommand(finished_game_id=4)


@pytest.mark.parametrize(
    "title",
    ["hello", "chess", "chess|move|e2e4", "chess|move|e9e4|1", "chess|move|e2e4|one", "chess|new", "chess|resign|1"],
)
def test_rejects_bad_titles(title):
    with pytest.raises(CommandError):
        parse_title(title)
