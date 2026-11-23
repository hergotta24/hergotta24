"""Command-line entry point and the one place where the real pieces get wired together.

    python -m chess_profile.cli handle-issue --title "chess|move|e2e4|1" --user bob --issue 5 --dry-run
    python -m chess_profile.cli reply --reply-file reply.json
    python -m chess_profile.cli remind [--force] [--dry-run]
    python -m chess_profile.cli sweep [--dry-run]
    python -m chess_profile.cli render
    python -m chess_profile.cli reset --alex-color black --yes
    python -m chess_profile.cli play-local
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from .config import CONFIG_FILE, ChessConfig, RepoPaths, load_config
from .game_service import GameService, Reply, utc_now
from .github_io import ConsoleIssueClient, GitHubIssueClient, IssueClient
from .readme import ChessSectionBuilder, IssueLinks, ReadmeUpdater
from .renderer import BoardImageStore, PngBoardRenderer
from .rules import ChessRules
from .state import ALEX, BLACK, WHITE, JsonStateStore
from .turn_policy import AlexVsCrowdPolicy


def build_service(root: Path, config: ChessConfig, clock=utc_now) -> GameService:
    paths = RepoPaths(root)
    links = IssueLinks(config.repo)
    return GameService(
        config=config,
        store=JsonStateStore(paths.state_file),
        rules=ChessRules(),
        policy=AlexVsCrowdPolicy(config),
        renderer=PngBoardRenderer(),
        images=BoardImageStore(root, paths.images_dir),
        readme=ReadmeUpdater(paths.readme, ChessSectionBuilder(config, links)),
        links=links,
        clock=clock,
    )


def _issue_client(config: ChessConfig, dry_run: bool) -> IssueClient:
    if dry_run:
        return ConsoleIssueClient()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set (use --dry-run to run locally).")
    return GitHubIssueClient(config.repo, token)


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252 and choke on emoji
    parser = argparse.ArgumentParser(prog="chess_profile")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repo root (default: current folder)")
    sub = parser.add_subparsers(dest="command", required=True)

    handle = sub.add_parser("handle-issue", help="process a chess|... issue")
    handle.add_argument("--title", required=True)
    handle.add_argument("--user", required=True)
    handle.add_argument("--issue", type=int, required=True)
    handle.add_argument("--reply-file", type=Path, help="where to save the reply for the 'reply' step")
    handle.add_argument("--dry-run", action="store_true", help="run on a scratch copy and print the reply")

    reply = sub.add_parser("reply", help="post a saved reply and close the issue")
    reply.add_argument("--reply-file", type=Path, required=True)
    reply.add_argument("--issue", type=int, required=True)

    remind = sub.add_parser("remind", help="ping the owner if a move has been waiting too long")
    remind.add_argument("--force", action="store_true")
    remind.add_argument("--dry-run", action="store_true")

    sweep = sub.add_parser("sweep", help="close chess issues that never got a reply")
    sweep.add_argument("--dry-run", action="store_true")

    sub.add_parser("render", help="redraw the board and README from saved state")

    reset = sub.add_parser("reset", help="wipe the record and start game 1")
    reset.add_argument("--alex-color", choices=[WHITE, BLACK], default=BLACK)
    reset.add_argument("--yes", action="store_true", help="confirm wiping the saved game and record")

    play = sub.add_parser("play-local", help="play a full game in the terminal against a temp copy")
    play.add_argument("--workdir", type=Path, help="folder for the temp copy (default: a new temp folder)")

    args = parser.parse_args(argv)
    root = args.root.resolve()

    if args.command == "play-local":
        return play_local(root, args.workdir)

    if getattr(args, "dry_run", False):
        root = scratch_copy(root)
        print(f"(dry run: working on a scratch copy in {root}; your repo is untouched)")
    config = load_config(root)
    service = build_service(root, config)

    if args.command == "handle-issue":
        result = service.handle_issue(args.title, args.user, args.issue)
        if args.dry_run or not args.reply_file:
            print(("ACCEPTED" if result.accepted else "REJECTED") + "\n" + result.body)
        else:
            args.reply_file.write_text(json.dumps(result.__dict__), encoding="utf-8")
        return 0
    if args.command == "reply":
        return post_reply(config, args.reply_file, args.issue, push_ok=os.environ.get("PUSH_OK") == "true")
    if args.command == "remind":
        pinged = service.remind(_issue_client(config, args.dry_run), force=args.force)
        print("Reminder sent." if pinged else "No reminder needed.")
        return 0
    if args.command == "sweep":
        closed = service.sweep_stray_issues(_issue_client(config, args.dry_run))
        print(f"Closed stray issues: {closed}" if closed else "No stray chess issues.")
        return 0
    if args.command == "render":
        service.refresh()
        print("README and board redrawn.")
        return 0
    if args.command == "reset":
        if not args.yes:
            print("This wipes the current game AND the record. Re-run with --yes to confirm.")
            return 1
        service.reset(args.alex_color)
        print(f"Reset to game 1 (Alex plays {args.alex_color}).")
        return 0
    return 1


def scratch_copy(root: Path) -> Path:
    """Copies the files the game reads and writes into a temp folder."""
    target = Path(tempfile.mkdtemp(prefix="chess-dry-run-"))
    shutil.copy(root / CONFIG_FILE, target / CONFIG_FILE)
    shutil.copy(root / "README.md", target / "README.md")
    paths, copy = RepoPaths(root), RepoPaths(target)
    copy.state_file.parent.mkdir(parents=True)
    shutil.copy(paths.state_file, copy.state_file)
    if paths.images_dir.exists():
        shutil.copytree(paths.images_dir, copy.images_dir)
    return target


def post_reply(config: ChessConfig, reply_file: Path, issue: int, push_ok: bool) -> int:
    client = _issue_client(config, dry_run=False)
    if not reply_file.exists():
        client.comment(issue, f"⚠️ Something went wrong reading this move. @{config.owner} will take a look.")
        return 1
    reply = Reply(**json.loads(reply_file.read_text(encoding="utf-8")))
    if reply.accepted and not push_ok:
        client.comment(issue, f"⚠️ The move was valid but couldn't be saved. Please try again. (@{config.owner} has been pinged.)")
        return 1
    client.comment(reply.issue, reply.body)
    client.close(reply.issue, reply.close_reason)
    return 0


# ---- local play ---------------------------------------------------------

LOCAL_HELP = """Commands:
  e4 / Nf3 / e2e4      move for whoever's turn it is (crowd moves rotate between two fake users)
  @bob e4              move as a specific GitHub user (try it to test the back-to-back rule)
  new                  start the next game (after one ends)
  remind               force the 'your move' reminder
  help / quit"""


def play_local(source_root: Path, workdir: Optional[Path]) -> int:
    """Plays through the real GameService against a throwaway copy of the repo files."""
    work = workdir or Path(tempfile.mkdtemp(prefix="chess-local-"))
    work.mkdir(parents=True, exist_ok=True)
    shutil.copy(source_root / CONFIG_FILE, work / CONFIG_FILE)
    shutil.copy(source_root / "README.md", work / "README.md")
    config = load_config(work, env={})
    service = build_service(work, config)
    service.reset(BLACK)
    issues = ConsoleIssueClient()
    rules = ChessRules()
    store = JsonStateStore(RepoPaths(work).state_file)
    crowd_users = ["crowd-alice", "crowd-bob"]
    issue_number = 0

    print(f"Local game in {work}\nOpen {work / 'README.md'} in VS Code (Ctrl+Shift+V) to see the page.\n{LOCAL_HELP}\n")
    while True:
        state = store.load()
        game = state.game
        board = rules.board_for(m.uci for m in game.moves)
        print("\n" + board.unicode(invert_color=True, borders=False) + "\n")
        print(f"Record {state.record.wins}W {state.record.losses}L {state.record.draws}D | board image: {work / (state.board_image or '')}")
        if game.is_active:
            prompt = f"Game {game.id}, {game.side_to_move} to move ({game.color_to_move}) > "
        else:
            prompt = f"Game {game.id} over ({game.result} by {game.result_reason}). Type 'new' or 'quit' > "
        try:
            line = input(prompt).strip()
        except EOFError:
            return 0
        if not line:
            continue
        if line in ("quit", "exit", "q"):
            return 0
        if line == "help":
            print(LOCAL_HELP)
            continue
        if line == "remind":
            print("Reminder sent." if service.remind(issues, force=True) else "No reminder: it's not Alex's turn.")
            continue
        issue_number += 1
        if line == "new":
            title, user = f"chess|new|{game.id}", crowd_users[0]
        else:
            user = None
            if line.startswith("@") and " " in line:
                user, line = line[1:].split(" ", 1)
            uci = rules.parse_any(board, line) or line
            if user is None:
                if game.side_to_move == ALEX:
                    user = config.owner
                else:
                    user = next(u for u in crowd_users if u != game.last_crowd_mover)
            title = f"chess|move|{uci}|{game.id}"
        print(f"(issue #{issue_number} by @{user}: {title})")
        print(service.handle_issue(title, user, issue_number).body)


if __name__ == "__main__":
    sys.exit(main())
