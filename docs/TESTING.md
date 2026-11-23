# Test Cases

A cumulative list of manual checks. Add new ones and never delete old ones. Mark obsolete cases ~~struck~~ with a date and reason. The automated suite is `.venv\Scripts\python -m pytest -q` (see [chess.md](chess.md) for setup).

## Chess: local

- [ ] **TC-001 — Automated suite passes** (added 2026-11-20, feature/chess-profile)
  - **Setup:** `py -3.12 -m venv .venv; .venv\Scripts\pip install -r requirements-dev.txt` (updated 2026-11-23: the PNG renderer needs Python 3.10+; an existing 3.9 `.venv` must be recreated)
  - **Steps:** 1. `.venv\Scripts\python -m pytest -q`
  - **Expected:** all tests pass. They include full scripted games: crowd checkmate, Alex checkmate, stalemate, threefold repetition, and promotion.
- [ ] **TC-002 — Play a full local game** (added 2026-11-20, feature/chess-profile)
  - **Setup:** TC-001 setup
  - **Steps:** 1. `.venv\Scripts\python -m chess_profile.cli play-local` 2. Enter `f3`, `e5`, `g4`, `Qh4#` 3. Enter `new`
  - **Expected:** each move prints a ✅ reply. After `Qh4#` it prints "Alex wins by checkmate" and the record shows `1W 0L 0D`. `new` starts game 2 with Alex as White.
- [ ] **TC-003 — Local README preview** (added 2026-11-20, feature/chess-profile)
  - **Setup:** a `play-local` game with a few moves made
  - **Steps:** 1. Open the `README.md` in the temp folder that `play-local` printed 2. Press Ctrl+Shift+V in VS Code
  - **Expected:** the chess section shows the board image, whose turn it is, a move table (or "Waiting on Alex" with a collapsed link list), the record, the leaderboard, and the Tim Burgan credit.
- [ ] **TC-004 — Back-to-back rule (local)** (added 2026-11-20, feature/chess-profile)
  - **Setup:** `play-local`
  - **Steps:** 1. `@bob e4` 2. `e5` (Alex) 3. `@bob Nf3`
  - **Expected:** step 3 is rejected with "no back-to-back moves". `@carol Nf3` then works.
- [ ] **TC-005 — Dry run never touches the repo** (added 2026-11-20, feature/chess-profile)
  - **Setup:** clean `git status`
  - **Steps:** 1. `.venv\Scripts\python -m chess_profile.cli handle-issue --title "chess|move|e2e4|1" --user someone --issue 0 --dry-run` 2. `git status`
  - **Expected:** it prints `ACCEPTED` and the reply, and `git status` is still clean.

## Chess: private sandbox (real GitHub, before go-live)

- [ ] **TC-006 — Your move via link** (added 2026-11-20, feature/chess-profile)
  - **Setup:** private `hergotta24/chess-sandbox` with variable `CHESS_TEST_MODE=true`
  - **Steps:** 1. Open the sandbox README 2. Click a crowd move (e.g. **e4**) 3. Press **Submit new issue** 4. Wait about 1 minute
  - **Expected:** the bot comments "✅ @hergotta24 played **e4** for the crowd" and closes the issue. The README board shows e4 with the last move highlighted, and the README now says "Waiting on Alex".
- [ ] **TC-007 — Full game on GitHub** (added 2026-11-20, feature/chess-profile)
  - **Setup:** TC-006
  - **Steps:** 1. Play both sides by clicking links until the game ends (fastest: f3, e5, g4, Qh4#) 2. Click **Start game 2** and submit
  - **Expected:** the final issue reply says who won. The README shows the result and the record. Game 2 starts with the colors flipped.
- [ ] **TC-008 — Rejections on GitHub** (added 2026-11-20, feature/chess-profile)
  - **Setup:** TC-006
  - **Steps:** 1. Open an issue titled `chess|move|e2e5|<current game>` 2. Open an issue titled `chess|move|e2e4|99`
  - **Expected:** both get a ❌ comment explaining why, are closed as "not planned", and the README doesn't change.
- [ ] **TC-009 — Reminder ping** (added 2026-11-20, feature/chess-profile)
  - **Setup:** sandbox with Alex to move
  - **Steps:** 1. Actions → **Chess reminder** → Run workflow with **force** checked
  - **Expected:** a "♟ Your move, Alex" issue appears with an `@hergotta24` comment, and you get a GitHub notification. Running it again adds a comment to the same issue.
- [ ] **TC-010 — Phone flow** (added 2026-11-20, feature/chess-profile)
  - **Setup:** GitHub mobile app or a phone browser, logged in
  - **Steps:** 1. Open the sandbox README on your phone 2. Tap a move link and submit
  - **Expected:** the move is played, same as TC-006.

## Chess: go-live (profile repo)

- [ ] **TC-011 — Live smoke move** (added 2026-11-20, feature/chess-profile)
  - **Setup:** PR merged into `hergotta24/hergotta24`, no `CHESS_TEST_MODE` variable
  - **Steps:** 1. A second account (or a friend) clicks a crowd move on github.com/hergotta24 2. You click your reply move
  - **Expected:** both moves are applied, you get notified on your turn, and there's no 🧪 banner on the page.
- [ ] **TC-012 — Owner can't move for the crowd (live)** (added 2026-11-20, feature/chess-profile)
  - **Setup:** live, crowd's turn
  - **Steps:** 1. Logged in as hergotta24, click a crowd move and submit
  - **Expected:** ❌ "It's the crowd's turn, Alex can't move for the crowd."

## Profile page

- [ ] **TC-013 — Chess-only profile page** (added 2026-11-21, feature/chess-profile)
  - **Setup:** none
  - **Steps:** 1. Open `README.md` in VS Code preview (or the sandbox README on GitHub)
  - **Expected:** only the intro, the chess section with the Tim Burgan credit, and the "How the chess bot works" link. No "Also building" or "Built with AI agents" sections, and no token-usage image.

## Board image (PNG)

- [ ] **TC-014 — Board shows on a restrictive work browser** (added 2026-11-23, fix/chessboard-profile-rendering)
  - **Setup:** PR merged; the work laptop/browser that previously showed only the alt text
  - **Steps:** 1. Open https://github.com/hergotta24 2. Hard-refresh (Ctrl+F5)
  - **Expected:** the board image appears (not "Current chess board, game 1" alt text). Right-click → Open image in new tab shows a `.png` URL.
- [ ] **TC-015 — Board file is a real PNG** (added 2026-11-23, fix/chessboard-profile-rendering)
  - **Setup:** TC-001 setup
  - **Steps:** 1. `.venv\Scripts\python -c "from PIL import Image; im=Image.open('assets/chess/board-1-0.png'); print(im.format, im.size)"` 2. `Get-ChildItem assets\chess`
  - **Expected:** prints `PNG (840, 840)`; the folder holds exactly one `board-*.png` and no `.svg`. Backed by `test_board_image_is_a_real_png_at_2x_display_size`.
- [ ] **TC-016 — Each move writes a new PNG and README points at it** (added 2026-11-23, fix/chessboard-profile-rendering)
  - **Setup:** TC-001 setup
  - **Steps:** 1. `.venv\Scripts\python -m chess_profile.cli play-local` 2. Enter `e4` 3. Open the printed temp folder's `assets\chess` and `README.md`
  - **Expected:** only `board-1-1.png` exists, the README `<img>` uses it, and e2/e4 are highlighted yellow. Backed by `test_readme_embeds_png_board_not_svg`.
- [ ] **TC-017 — Legacy SVG state migrates on render** (added 2026-11-23, fix/chessboard-profile-rendering)
  - **Setup:** a scratch copy of the repo whose `state.json` points at `assets/chess/board-1-0.svg`
  - **Steps:** 1. `.venv\Scripts\python -m chess_profile.cli --root <copy> render`
  - **Expected:** the `.svg` is deleted, `board-1-0.png` is written, and `state.json`/README reference the `.png`. Backed by `test_render_migrates_a_legacy_svg_board_to_png`.
