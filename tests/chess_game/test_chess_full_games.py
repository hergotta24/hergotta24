"""Complete games from first move to result, then the next game."""
from chess_profile.state import ALEX, CROWD

SCHOLARS_MATE = ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7#"]  # white (crowd) wins
FOOLS_MATE = ["f3", "e5", "g4", "Qh4#"]  # black (Alex) wins
STALEMATE = ["e3", "a5", "Qh5", "Ra6", "Qxa5", "h5", "h4", "Rah6", "Qxc7", "f6", "Qxd7+", "Kf7",
             "Qxb7", "Qd3", "Qxb8", "Qh7", "Qxc8", "Kg6", "Qe6"]
REPETITION = ["Nf3", "Nf6", "Ng1", "Ng8", "Nf3", "Nf6", "Ng1", "Ng8"]


def test_crowd_wins_by_checkmate(harness):
    reply = harness.play(*SCHOLARS_MATE)
    state = harness.state
    assert state.game.status == "finished"
    assert (state.game.result, state.game.result_reason) == (CROWD, "checkmate")
    assert (state.record.wins, state.record.losses, state.record.draws) == (0, 1, 0)
    assert "The crowd wins" in reply.body
    assert "The crowd wins by checkmate" in harness.readme
    assert "chess%7Cnew%7C1" in harness.readme  # start-next-game link
    assert "| Piece | Moves |" not in harness.readme  # no move links once it's over


def test_alex_wins_by_checkmate(harness):
    harness.play(*FOOLS_MATE)
    state = harness.state
    assert state.game.result == ALEX
    assert (state.record.wins, state.record.losses) == (1, 0)
    assert "Alex wins by checkmate" in harness.readme


def test_stalemate_is_a_draw(harness):
    harness.play(*STALEMATE)
    state = harness.state
    assert (state.game.result, state.game.result_reason) == ("draw", "stalemate")
    assert state.record.draws == 1


def test_threefold_repetition_ends_in_draw(harness):
    harness.play(*REPETITION)
    state = harness.state
    assert (state.game.result, state.game.result_reason) == ("draw", "threefold repetition")


def test_moves_after_game_over_are_rejected(harness):
    harness.play(*SCHOLARS_MATE)
    reply = harness.raw("chess|move|a7a6|1", "alice")
    assert not reply.accepted and "already over" in reply.body


def test_new_game_flips_colors_and_keeps_record(harness):
    harness.play(*SCHOLARS_MATE)
    reply = harness.raw("chess|new|1", "carol")
    assert reply.accepted and "Game 2 has started" in reply.body
    state = harness.state
    assert (state.game.id, state.game.alex_color, state.game.side_to_move) == (2, "white", ALEX)
    assert state.record.losses == 1
    assert state.crowd_moves  # leaderboard survives between games
    # second "new" click for the same finished game is a duplicate
    assert not harness.raw("chess|new|1", "dave").accepted
    # game 2: Alex is white and moves first
    assert harness.move("e4").accepted
    assert harness.state.game.moves[0].side == ALEX


def test_new_game_rejected_while_game_in_progress(harness):
    reply = harness.raw("chess|new|1", "alice")
    assert not reply.accepted and "still in progress" in reply.body


def test_two_full_games_record_accumulates(harness):
    harness.play(*SCHOLARS_MATE)  # game 1: Alex black, loses
    harness.raw("chess|new|1", "carol")
    harness.play(*SCHOLARS_MATE)  # game 2: Alex white, wins
    record = harness.state.record
    assert (record.wins, record.losses, record.draws) == (1, 1, 0)
    assert "**Alex vs the crowd:** 1 W · 1 L · 0 D" in harness.readme


def test_promotion_move(harness):
    # crowd's a-pawn marches and promotes on b8 by capture
    harness.play("a4", "h5", "a5", "h4", "a6", "h3", "axb7", "hxg2")
    reply = harness.move("bxa8=Q")
    assert reply.accepted and "bxa8=Q" in reply.body
