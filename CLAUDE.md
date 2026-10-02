# Grizzly Rips Match Centre

FC 27 Pro Clubs analysis app for the club **Grizzly Rips** (PS5, EA club_id 882969). Runs entirely on GitHub; nothing runs locally.

- Repo: https://github.com/sce22/grizzly-rips (public; GitHub Pages serves `docs/`)
- Site: https://sce22.github.io/grizzly-rips/
- Owner's gamertag: **tuxedo_slide** (`notify.my_player`). Teammates: BellyTb1 (Troy), PhogsToffees.

## How it runs
- `.github/workflows/sync.yml` ("Match watcher"): `python -m fcapp.watch` polls EA every minute for up to ~5.5h, then dispatches its own successor (GitHub's cron lagged by hours on this repo; the cron is only a backup). On a new match it rebuilds `docs/`, commits/pushes as `fc-sync-bot`, waits for Pages, then sends notifications. It exits early when non-bot commits land so the next run picks up new code.
- EA's feed is unofficial and returns only the last 10 matches per match type, hence the minute polling. It blocks plain HTTP clients; `curl_cffi` with Chrome impersonation gets through (works from GitHub runners).
- `test-text.yml` ("Send test message", inputs: channel, players) and `invite.yml` ("Invite a player") are manual.

## Notifications
- ntfy push only. Each player's private topic is derived from the `NTFY_SECRET` repo secret (`fcapp/push.py`). Only players who appeared in a match are notified. Topic names must never be printed or committed (public repo, public logs).
- SMS code still exists but is off (`notify.sms: false`) and its secrets were deleted. Verizon email-to-text truncated at ~130 chars and dropped follow-up messages.
- The user wants to be told explicitly, with the time (Central), whenever a test notification is sent to their phone.

## Daily Summary
- `fcapp/daily.py`: at 10:45pm CT (window 10:45pm-10:45pm) any day with 3+ matches gets a Coach Lasso pep talk (2-3 min, ~330-430 words), letter grade from an internal 0-20 scale (never shown), key stats and a league-table snapshot (EA `settings` thresholds + `overallStats.lastMatch0-9` = current 10-game season). Pushed to that day's players; saved in `data/daily/<date>.json`; shown on the Daily tab with a grade calendar. Nightly sends started 2026-10-02 (`daily.start_date`).
- League ladder (`fcapp/league.py`): EA's division fields use the old 10-division format and lag, so we track FC 27's ladder ourselves from a user-confirmed seed (`data/league_state.json`), advanced by each league match. Rules (confirmed by the club): Div 5 -> 4 -> 3 -> 2 -> 1 -> Elite; points phase targets 5: 7, 4: 9, 3: 12, 2: 14, 1: 18, Elite unlimited; a loss (never a draw) costs one of 3 chances, shown as 3 circles - green = left, black = lost; promotion matches in every division (5->4 win 1 of 3, 4->3 2 of 3, 3->2 3 of 4, 2->1 4 of 4, 1->Elite 5 of 5); failing means a relegation match where a win or draw stays up, resets chances to 3 and restores the points from before the slip (after a failed series that's the full target, so a fresh series starts). The ladder never sends notifications; it lives on the Matches tab. Wording: "Promotion", "Must win X out of Y" (Y = matches left). Correct it with Actions -> "Update league status". EA result bit 16384 is NOT a target flag.
- Speech by Claude (`claude-opus-5-5`, fallbacks "default") when the `ANTHROPIC_API_KEY` secret exists, else the built-in writer. Summaries are written once and never regenerated.

## Code map
- `fcapp/ea_client.py` EA API · `store.py` archive in `data/seasons/season-NN/` (never delete) · `analysis.py` grading + rating model · `playbook.py` benchmarks/tips · `coach.py` + `lasso.py` Coach Lasso voice · `build_site.py` → `docs/` · `run.py` pipeline · `watch.py` watcher · `push.py`/`invite.py` ntfy.
- Seasons: 5 weeks, roll over Thursday midnight Central; Season 1 = Sep 17 to Oct 22, 2026 (`config.json`).
- Rating model: per-position ridge regression shrunk toward league baseline (worth 30 matches, `analysis.prior_matches`), retrained from the full archive every rebuild; snapshot in `data/model.json`. Benchmarks stay league-wide on purpose.
- Stat reference (fields, decoded event codes, regression findings): `reference/ea-stats-reference.html`.

## Voice and content rules (from the user)
- All insights are written as Coach Lasso: warm, folksy, Ted Lasso-style framing, but every bullet tied to a real number and grounded in soccer coaching principles. No direct show quotes needed.
- Player notes: 6-10 bullets split between "did well" and "work on", personal to that player, one teammate line when it fits, a drill, signed "- Coach Lasso".
- Avoid repetition across everything a reader sees: `lasso.py` picks phrases least-recently-used club-wide, in match order. Add variants to the pools rather than reusing lines.
- Tapping a notification opens it in ntfy (no click URL); website only via the action buttons.

## Working on it
- The Desktop copy falls behind GitHub as the bot commits matches: `git pull --rebase` before editing, then push. Rebuild locally with `python -m fcapp.run --no-fetch --no-notify` (needs `pip install -r requirements.txt`).
- Commits end with a `Co-Authored-By` line when Claude makes them.
