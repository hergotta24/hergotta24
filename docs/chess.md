# Profile chess: how it works

Visitors to the profile play one shared game of chess together, as a single team ("the crowd"), against Alex.

**Credit:** this is inspired by [Tim Burgan's community chess game](https://github.com/timburgan/timburgan) ([@timburgan](https://github.com/timburgan)). The core idea comes from Tim: README links open a pre-filled issue and a GitHub Action plays the move. What's different here:

- Tim's game is crowd vs crowd. This one is the crowd vs Alex.
- The board is a generated SVG image.
- There are turn rules: no back-to-back crowd moves, and reminders when Alex owes a move.
- Alex keeps a running W-L-D record and the README shows a crowd leaderboard.

The code in this repo was written from scratch.

## The flow

1. **The link.** `README.md` shows the board image and every legal move as a link. A link opens a new issue titled `chess|move|<uci>|<game>`, for example `chess|move|e2e4|1`.
2. **The workflow.** Opening the issue triggers `.github/workflows/chess.yml`, which runs `python -m chess_profile.cli handle-issue`. That command:
   - parses the title (`commands.py`);
   - checks the move is allowed. It must be the current game. On Alex's turn only Alex may move. On the crowd's turn Alex may not move, and neither may whoever made the last crowd move (`turn_policy.py`). The move must also be legal chess (`rules.py`).
   - updates `data/chess/state.json` and draws a new `assets/chess/board-<game>-<ply>.svg` (`renderer.py`). Each position gets a new file name so GitHub's image cache can't show a stale board.
   - rewrites the README between `<!-- CHESS:START -->` and `<!-- CHESS:END -->` (`readme.py`).
3. **Commit, then reply.** `scripts/chess_commit_push.sh` commits and pushes, retrying if the nightly token-widget commit landed first. Only *after* the push does the `reply` step comment on the issue and close it, so the bot never claims a move that wasn't saved.
4. **Game over.** On checkmate, stalemate, threefold repetition, the fifty-move rule or insufficient material, the record updates and the README shows a **Start game N+1** link (`chess|new|N`). The new game flips Alex's color.
5. **Reminders.** Every day `.github/workflows/chess-reminder.yml` runs. If Alex has owed a move for 3+ days, it comments `@hergotta24` on a "♟ Your move, Alex" issue. That issue is created once and then reused. The same job also closes any `chess|` issue that never got a reply, which can happen if many moves land at the same moment.

## Code map

| File | Job |
| --- | --- |
| `chess_profile/cli.py` | Command-line entry point. Wires the real pieces together. |
| `chess_profile/game_service.py` | The orchestrator: handle a command, finish games, reminders, sweep |
| `chess_profile/commands.py` | Issue title → command |
| `chess_profile/state.py` | Saved game data + `JsonStateStore` |
| `chess_profile/rules.py` | Chess rules (wraps python-chess) |
| `chess_profile/turn_policy.py` | Who may move now |
| `chess_profile/renderer.py` | SVG board + image file management |
| `chess_profile/readme.py` | Builds and swaps the README section |
| `chess_profile/github_io.py` | GitHub issues API (plus a console fake for local runs) |
| `chess.config.json` | Owner, display name, reminder days, leaderboard size, test mode |

The service depends only on interfaces, so tests and local play swap in fakes. To change a rule (say, a voting window instead of first-move-wins), you'd add a new `TurnPolicy` and wire it up in `cli.py`.

## Running it locally

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest -q                      # all tests, including full scripted games
.venv\Scripts\python -m chess_profile.cli play-local    # play a whole game in the terminal
```

`play-local` runs the real game code against a temp copy of the repo, so you can open that copy's `README.md` in VS Code's Markdown preview to see the page. Every `--dry-run` command also works on a scratch copy and never touches your repo. VS Code launch configs for all of this are in `.vscode/launch.json`.

## Test mode (the private sandbox)

Set the repo variable `CHESS_TEST_MODE=true` (Settings → Secrets and variables → Actions → Variables). Test mode lets the owner move for **both** sides and turns off the back-to-back rule, so one person can play a full game by clicking links. The README shows a 🧪 banner while it's on. The profile repo must never set this.

## Maintenance

- **Redraw** the README/board from saved state: `python -m chess_profile.cli render`
- **Start over** with game 1 and a wiped record: `python -m chess_profile.cli reset --alex-color black --yes`, then commit
- **Fix a bad state by hand:** edit `data/chess/state.json`, run `render`, then commit
