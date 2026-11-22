"""README section, board images, leaderboard, reminders, stray-issue sweep, CLI reply file."""
import json

import pytest

from chess_profile.cli import main
from chess_profile.github_io import ConsoleIssueClient, OpenIssue
from chess_profile.readme import replace_section

from .conftest import OWNER


def test_readme_section_replaced_and_rest_kept(harness):
    text = harness.readme
    assert text.startswith("# Hi") and "## Also building" in text
    assert "## Play chess against me" in text
    assert "Inspired by" in text and "timburgan" in text


def test_readme_move_links_are_prefilled_issue_links(harness):
    assert f"https://github.com/{OWNER}/{OWNER}/issues/new?title=chess%7Cmove%7Ce2e4%7C1" in harness.readme


def test_readme_hides_alex_links_in_details_on_his_turn(harness):
    harness.move("e4")
    assert "Waiting on Alex" in harness.readme
    assert f"only @{OWNER} can play these" in harness.readme


def test_replace_section_requires_markers():
    with pytest.raises(ValueError):
        replace_section("# no markers", "x")


def test_board_image_new_file_each_move_old_one_deleted(harness):
    first = harness.state.board_image
    harness.move("e4")
    second = harness.state.board_image
    assert first != second
    assert not (harness.root / first).exists()
    assert (harness.root / second).read_text(encoding="utf-8").startswith("<svg")
    assert second in harness.readme


def test_leaderboard_sorted_and_capped(harness):
    # 7 different crowd players, alice plays twice
    players = ["alice", "bob", "alice", "carol", "dave", "erin", "frank", "gina"]
    sans = ["a3", "h6", "b3", "h5", "c3", "h4", "d3", "g6", "e3", "g5", "f3", "f6", "g3", "f5", "h3", "e6"]
    for i, san in enumerate(sans):
        user = players[i // 2] if i % 2 == 0 else OWNER
        assert harness.move(san, user=user).accepted, (san, user)
    assert harness.state.crowd_moves["alice"] == 2
    readme = harness.readme
    assert "| 1 | @alice | 2 |" in readme
    assert "| 5 |" in readme and "| 6 |" not in readme


def test_test_mode_banner(test_mode_harness):
    assert "Test mode" in test_mode_harness.readme


def test_reminder_waits_three_days_then_pings_and_reuses_issue(harness):
    issues = ConsoleIssueClient(echo=False)
    assert not harness.service.remind(issues)  # crowd's turn: nothing to remind
    harness.move("e4")
    harness.clock.advance(days=2, hours=23)
    assert not harness.service.remind(issues)
    harness.clock.advance(hours=1)
    assert harness.service.remind(issues)
    kinds = [c[0] for c in issues.calls]
    assert kinds == ["create", "comment"]
    assert f"@{OWNER}" in issues.calls[1][2]
    assert not harness.service.remind(issues)  # just pinged
    harness.clock.advance(days=3)
    assert harness.service.remind(issues)
    assert [c[0] for c in issues.calls] == ["create", "comment", "comment"]  # same issue reused
    assert issues.calls[2][1] == issues.calls[0][1]


def test_reminder_force_and_reset_after_alex_moves(harness):
    issues = ConsoleIssueClient(echo=False)
    harness.move("e4")
    assert harness.service.remind(issues, force=True)
    harness.move("e5")
    assert harness.state.game.last_reminder_at is None
    assert not harness.service.remind(issues, force=True)  # crowd's turn now


def test_sweep_closes_only_old_chess_issues(harness):
    issues = ConsoleIssueClient(echo=False, issues=[
        OpenIssue(1, "chess|move|e2e4|1", "2026-11-20T11:00:00Z"),  # an hour old
        OpenIssue(2, "chess|move|d2d4|1", "2026-11-20T11:58:00Z"),  # 2 minutes old: maybe still running
        OpenIssue(3, "Love the profile!", "2026-11-01T00:00:00Z"),
    ])
    assert harness.service.sweep_stray_issues(issues) == [1]
    assert ("close", 1, "not_planned") in issues.calls


def test_cli_handle_issue_writes_reply_file(harness, tmp_path):
    reply_file = tmp_path / "reply.json"
    code = main(["--root", str(harness.root), "handle-issue", "--title", "chess|move|e2e4|1",
                 "--user", "alice", "--issue", "42", "--reply-file", str(reply_file)])
    assert code == 0
    reply = json.loads(reply_file.read_text(encoding="utf-8"))
    assert reply["issue"] == 42 and reply["accepted"] is True


def test_cli_reset_requires_yes(harness, capsys):
    assert main(["--root", str(harness.root), "reset"]) == 1
    assert "--yes" in capsys.readouterr().out


def test_cli_dry_run_never_touches_the_repo(harness):
    before = (harness.root / "data" / "chess" / "state.json").read_text(encoding="utf-8")
    readme_before = harness.readme
    assert main(["--root", str(harness.root), "handle-issue", "--title", "chess|move|e2e4|1",
                 "--user", "alice", "--issue", "1", "--dry-run"]) == 0
    assert (harness.root / "data" / "chess" / "state.json").read_text(encoding="utf-8") == before
    assert harness.readme == readme_before
