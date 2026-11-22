"""Who may move when: Alex vs crowd, no back-to-back, stale links, illegal moves."""
from chess_profile.state import ALEX, CROWD

from .conftest import OWNER


def test_new_game_has_crowd_as_white_moving_first(harness):
    game = harness.state.game
    assert (game.id, game.alex_color, game.side_to_move) == (1, "black", CROWD)


def test_crowd_move_then_alex_reply(harness):
    reply = harness.move("e4", user="alice")
    assert reply.accepted
    assert f"@{OWNER}, it's your move" in reply.body
    assert harness.state.game.side_to_move == ALEX
    reply = harness.move("e5", user=OWNER)
    assert reply.accepted
    assert "The crowd is up" in reply.body


def test_alex_cannot_move_for_the_crowd(harness):
    reply = harness.move("e4", user=OWNER)
    assert not reply.accepted and "crowd's turn" in reply.body
    assert harness.state.game.moves == []


def test_crowd_cannot_move_on_alexs_turn(harness):
    harness.move("e4", user="alice")
    reply = harness.move("e5", user="bob")
    assert not reply.accepted and "Alex's turn" in reply.body


def test_no_back_to_back_crowd_moves_case_insensitive(harness):
    harness.move("e4", user="alice")
    harness.move("e5", user=OWNER)
    reply = harness.move("Nf3", user="ALICE")
    assert not reply.accepted and "back-to-back" in reply.body
    assert harness.move("Nf3", user="bob").accepted


def test_illegal_move_rejected_and_state_unchanged(harness):
    reply = harness.raw("chess|move|e2e5|1", "alice")
    assert not reply.accepted and "isn't legal" in reply.body
    assert harness.state.game.moves == []


def test_stale_game_link_rejected(harness):
    reply = harness.raw("chess|move|e2e4|7", "alice")
    assert not reply.accepted and "game 7" in reply.body


def test_garbage_title_rejected(harness):
    reply = harness.raw("chess|dance|1", "alice")
    assert not reply.accepted
    assert reply.close_reason == "not_planned"


def test_first_valid_move_wins_second_is_rejected(harness):
    assert harness.move("e4", user="alice").accepted
    # bob clicked a link from the old page at the same time
    reply = harness.raw("chess|move|d2d4|1", "bob")
    assert not reply.accepted


def test_test_mode_lets_owner_play_both_sides(test_mode_harness):
    h = test_mode_harness
    for san in ["e4", "e5", "Nf3", "Nc6"]:
        assert h.move(san, user=OWNER).accepted
    assert h.state.crowd_moves == {OWNER: 2}


def test_test_mode_still_blocks_others_on_alexs_turn(test_mode_harness):
    h = test_mode_harness
    h.move("e4", user="alice")
    assert not h.move("e5", user="bob").accepted
