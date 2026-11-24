"""The orchestrator: takes a command, applies the rules, and publishes the result.

It only depends on interfaces (StateStore, TurnPolicy, BoardRenderer, IssueClient),
so tests and local play swap in fakes without changing this file.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, List

from .commands import CommandError, MoveCommand, NewGameCommand, parse_title
from .config import ChessConfig
from .github_io import IssueClient
from .readme import IssueLinks, ReadmeUpdater
from .renderer import BoardImageStore, BoardRenderer
from .rules import ChessRules, GameResult
from .state import ALEX, CROWD, ChessState, Game, MoveRecord, StateStore, other_color
from .turn_policy import TurnPolicy

Clock = Callable[[], datetime]
REMINDER_TITLE = "♟ Your move, Alex"
STRAY_ISSUE_MINUTES = 10


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


@dataclass(frozen=True)
class Reply:
    """What to say on the issue. Posted after the commit is pushed, so we never claim a move that didn't land."""

    issue: int
    body: str
    accepted: bool

    @property
    def close_reason(self) -> str:
        return "completed" if self.accepted else "not_planned"


class GameService:
    def __init__(
        self,
        config: ChessConfig,
        store: StateStore,
        rules: ChessRules,
        policy: TurnPolicy,
        renderer: BoardRenderer,
        images: BoardImageStore,
        readme: ReadmeUpdater,
        links: IssueLinks,
        clock: Clock = utc_now,
    ) -> None:
        self._config = config
        self._store = store
        self._rules = rules
        self._policy = policy
        self._renderer = renderer
        self._images = images
        self._readme = readme
        self._links = links
        self._clock = clock

    # ---- issue commands -------------------------------------------------

    def handle_issue(self, title: str, user: str, issue: int) -> Reply:
        try:
            command = parse_title(title)
        except CommandError as error:
            return self._reject(issue, str(error))
        state = self._store.load()
        if isinstance(command, MoveCommand):
            return self._move(state, command, user, issue)
        return self._new_game(state, command, issue)

    def _move(self, state: ChessState, command: MoveCommand, user: str, issue: int) -> Reply:
        game = state.game
        if command.game_id != game.id:
            return self._reject(issue, f"That link is from game {command.game_id}, but game {game.id} is the current one.")
        if not game.is_active:
            return self._reject(issue, f"Game {game.id} is already over. Start the next one from the README.")
        refusal = self._policy.rejection(game, user)
        if refusal:
            return self._reject(issue, refusal)

        board = self._rules.board_for(m.uci for m in game.moves)
        side = game.side_to_move
        san = self._rules.play(board, command.uci)
        if san is None:
            return self._reject(issue, f"`{command.uci}` isn't legal in the current position. Someone may have moved first.")

        now = _iso(self._clock())
        game.moves.append(MoveRecord(uci=command.uci, san=san, user=user, side=side, at=now))
        game.last_move_at = now
        game.last_reminder_at = None
        if side == CROWD:
            game.last_crowd_mover = user
            state.crowd_moves[user] = state.crowd_moves.get(user, 0) + 1

        result = self._rules.result(board)
        if result:
            self._finish(state, result)
        self._publish(state)
        return Reply(issue=issue, body=self._move_message(state, side, san, user), accepted=True)

    def _new_game(self, state: ChessState, command: NewGameCommand, issue: int) -> Reply:
        game = state.game
        if game.is_active:
            return self._reject(issue, f"Game {game.id} is still in progress. Make a move from the README instead.")
        if command.finished_game_id != game.id:
            return self._reject(issue, f"Game {game.id + 1} has already been started.")
        state.game = Game(id=game.id + 1, alex_color=other_color(game.alex_color), started_at=_iso(self._clock()))
        self._publish(state)
        new = state.game
        name = self._config.owner_display_name
        turn = "The crowd moves first" if new.side_to_move == CROWD else f"{name} moves first (@{self._config.owner})"
        body = (
            f"♟ Game {new.id} has started! The crowd plays {new.crowd_color.title()}, {name} plays "
            f"{new.alex_color.title()}. {turn}. [Go to the board]({self._links.board()})"
        )
        return Reply(issue=issue, body=body, accepted=True)

    def _finish(self, state: ChessState, result: GameResult) -> None:
        game = state.game
        game.status = "finished"
        game.result_reason = result.reason
        if result.winner is None:
            game.result = "draw"
            state.record.draws += 1
        elif result.winner == game.alex_color:
            game.result = ALEX
            state.record.wins += 1
        else:
            game.result = CROWD
            state.record.losses += 1

    def _move_message(self, state: ChessState, side: str, san: str, user: str) -> str:
        game = state.game
        name = self._config.owner_display_name
        board = self._links.board()
        if side == CROWD:
            text = f"✅ @{user} played **{san}** for the crowd in game {game.id}."
        else:
            text = f"✅ {name} played **{san}** in game {game.id}."
        if not game.is_active:
            outcome = {ALEX: f"{name} wins", CROWD: "The crowd wins 🎉"}.get(game.result, "It's a draw")
            return f"{text}\n\n🏁 **{outcome}** by {game.result_reason}. [Start the next game]({board})"
        if game.side_to_move == ALEX:
            return f"{text}\n\n@{self._config.owner}, it's your move! [Open the board]({board})"
        return f"{text}\n\nThe crowd is up. [Pick the next move]({board})"

    def _reject(self, issue: int, reason: str) -> Reply:
        return Reply(issue=issue, body=f"❌ {reason}\n\n[Back to the board]({self._links.board()})", accepted=False)

    # ---- publishing ----------------------------------------------------

    def _publish(self, state: ChessState) -> None:
        game = state.game
        board = self._rules.board_for(m.uci for m in game.moves)
        image = self._renderer.render(board, orientation=game.crowd_color)
        state.board_image = self._images.write(game.id, len(game.moves), image, self._renderer.extension)
        legal = self._rules.legal_moves(board) if game.is_active else []
        self._readme.update(state, legal)
        self._store.save(state)

    def refresh(self) -> None:
        """Redraw the board and README from the saved state (after editing the README by hand, or a reset)."""
        self._publish(self._store.load())

    def reset(self, alex_color: str) -> None:
        """Wipe everything and start game 1. Local use only."""
        self._publish(ChessState.fresh(alex_color=alex_color, now=_iso(self._clock())))

    # ---- scheduled jobs ------------------------------------------------

    def remind(self, issues: IssueClient, force: bool = False) -> bool:
        """Ping the owner if they've owed a move for `reminder_days`. Returns True if pinged."""
        state = self._store.load()
        game = state.game
        if not game.is_active or game.side_to_move != ALEX:
            return False
        since = _parse(game.last_reminder_at or game.last_move_at or game.started_at)
        if not force and self._clock() - since < timedelta(days=self._config.reminder_days):
            return False
        if state.reminder_issue is None:
            state.reminder_issue = issues.create_issue(
                REMINDER_TITLE.replace("Alex", self._config.owner_display_name),
                "The chess bot comments here when a move has been waiting a while. Leave this issue open.",
            )
        waiting = (game.last_move_at or game.started_at)[:10]
        last = f" The crowd played **{game.moves[-1].san}**." if game.moves else ""
        issues.comment(
            state.reminder_issue,
            f"⏰ @{self._config.owner}, game {game.id} has been waiting on your move since {waiting}.{last} "
            f"[Open the board]({self._links.board()})",
        )
        game.last_reminder_at = _iso(self._clock())
        self._store.save(state)
        return True

    def sweep_stray_issues(self, issues: IssueClient) -> List[int]:
        """Close chess issues that were never answered.

        If many moves arrive at once, GitHub can drop queued workflow runs, which
        leaves those issues open with no reply. This closes them politely.
        """
        cutoff = self._clock() - timedelta(minutes=STRAY_ISSUE_MINUTES)
        closed = []
        for item in issues.open_issues():
            if item.title.lower().startswith("chess|") and _parse(item.created_at) < cutoff:
                issues.comment(
                    item.number,
                    "⌛ This move didn't get processed. Another move probably landed at the same time. "
                    f"Please pick again from the [board]({self._links.board()}).",
                )
                issues.close(item.number, "not_planned")
                closed.append(item.number)
        return closed
