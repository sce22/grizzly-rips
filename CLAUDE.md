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
- New members: the first time a gamertag appears in our matches, `invite.invite_new_members` pushes their subscribe key to the owner's channel to forward (known members in `data/members.json`). Manual: Actions -> "Invite a player".
- SMS code still exists but is off (`notify.sms: false`) and its secrets were deleted. Verizon email-to-text truncated at ~130 chars and dropped follow-up messages.
- The user wants to be told explicitly, with the time (Central), whenever a test notification is sent to their phone.

## Daily Summary
- `fcapp/daily.py`: at 11:00pm CT (window 11pm-11pm) any day with at least one match gets a Coach Lasso pep talk (2-3 min, ~330-430 words), letter grade from an internal 0-20 scale (never shown), key stats and a league ladder snapshot (fcapp/league.py). Pushed to that day's players; saved in `data/daily/<date>.json`; shown on the Daily tab with a grade calendar. Nightly sends started 2026-10-02 (`daily.start_date`).
- League ladder (`fcapp/league.py`): EA's division fields use the old 10-division format and lag, so we track FC 27's ladder ourselves from a user-confirmed seed (`data/league_state.json`), advanced by each league match. Rules (confirmed by the club): Div 5 -> 4 -> 3 -> 2 -> 1 -> Elite; points phase targets 5: 7, 4: 9, 3: 12, 2: 16, 1: 18, Elite unlimited; a loss (never a draw) costs one of 3 chances, shown as 3 circles - green = left, black = lost; promotion matches in every division (5->4 win 1 of 3, 4->3 2 of 3, 3->2 3 of 4, 2->1 4 of 4, 1->Elite 5 of 5); a failed promotion series sends you back to 0 pts (3 chances) in the same division; losing all 3 chances in the points phase means a relegation match where a win or draw stays up, resets chances to 3 and restores the points where you left off, and a loss drops a division. The ladder never sends notifications; it lives on the Matches tab. Wording: "Promotion", "Must win X out of Y" (Y = matches left). Anyone can correct it in the app: the gear on the ladder card opens an editor (division, stage, points, points needed, chances, promotion results) that posts JSON to the ntfy topic `league.edit_topic`; `fcapp/ladder_edits.py` (run by the watcher every minute) validates and applies it via `set_league.apply_status` as of the newest league match, then rebuilds. Later matches carry on with the normal rules. (Actions -> "Update league status" still works.) EA result bit 16384 is NOT a target flag.
- Grading (`daily.score_day`, 10 = an ordinary day): results, margin and ratings on a fixed league scale (1.5 ppg, level GD, 6.8 rating = 10), blended with the team baseline, then ladder and conduct on top (`ladder_and_conduct`): dropping a division -4, promotion +3, ending the day facing a relegation match -1.5, failed promotion -1, rage quits -1 each (max -3). Oct 5 2026 (3-0-6, relegated from Div 2, relegation match in Div 3 next, 2 rage quits) = F, as the club agreed.
- The day's ladder story (`league.day_story`): ladder at the start and end of the day window plus events in between, from `data/league_seeds.json` (every confirmed seed, backfilled from git; `league.seed_for` picks the one in force at a timestamp). Each summary saves it as `ladder_day`.
- Each player's day (`daily.summarize_players`): totals, vs their usual, all-time numbers, a per-match log, and the strongest distinct `lowlights` (2-3) and `highlights` from the signals. Claude gets all of it (`daily.claude_facts`); the F-day tone lays into the team, gives every player 2-3 numbered failures, then turns warm and always ends on a high note. Built-in fallback: `scathing_speech`.
- Grades blend league standards with the team's own baseline (all matches before the day): weight n/(n+40), starting at 20 matches (`daily.team_baseline`). Claude gets the baseline as `our_usual`.
- Speech by Claude (`claude-opus-5-5`, fallbacks "default") when the `ANTHROPIC_API_KEY` secret exists, else the built-in writer. Summaries are written once and never regenerated.

## Code map
- `fcapp/ea_client.py` EA API · `store.py` archive in `data/seasons/season-NN/` (never delete) · `analysis.py` grading + rating model · `playbook.py` benchmarks/tips · `coach.py` + `lasso.py` Coach Lasso voice · `build_site.py` → `docs/` · `run.py` pipeline · `watch.py` watcher · `push.py`/`invite.py` ntfy.
- Seasons: 5 weeks, roll over Thursday midnight Central; Season 1 = Sep 17 to Oct 22, 2026 (`config.json`).
- Rating model: per-position ridge regression shrunk toward league baseline (worth 30 matches, `analysis.prior_matches`), retrained from the full archive every rebuild; snapshot in `data/model.json`. Benchmarks stay league-wide on purpose.
- Stat reference (fields, decoded event codes, regression findings): `reference/ea-stats-reference.html`.

## Signals, Good / Bad / Ugly, rage quits
- `fcapp/signals.py` checks every stat (20+ incl. derived goal involvements, on-ball actions, giveaways) against ~13 frames (usual, all-time, team, share, opponent humans, session, last match, season, wins, opponent average, club history at the position, benchmark, streaks) plus match context (scoreline, ladder stakes per match via `league.match_events`, opponent strength, session fatigue, rage quits, red cards, idle). ~220 checks per player-match; signals have side good/bad/ugly and a weight.
- Player notes keep 6-10 bullets in THE GOOD / THE BAD / THE UGLY (`lasso.build`): strongest first, one per stat family, Ugly (max 3): always for a rating under 6.7 (`lasso.UGLY_BELOW`; the worst individual Bad item moves there if nothing else qualifies), plus rage quits, red cards, collapses. Never show the number of checks anywhere - just the insights. Team-level facts use team framing (`lasso_ugly.TEAM_*`). Frames live in `fcapp/lasso_ugly.py`.
- Rage quit = the player's game clock (`gameTime`) stopped more than 60s before the match's last clock (`analysis.LEAVE_GRACE`), or a rating <= 3.0; never when we won by forfeit (opponent quit). EA can't tell a quit from a disconnect. `left_at` = minute they left. Ratings <= 3.0 count as 5.0 everywhere (raw kept as `raw_rating`); early leavers keep their real rating. Rage quits are excluded from model training and "your usual", shown on profiles (`rage_quits`) and in daily summaries.
- Banner (player card chip): only a player's 5 best and 5 worst matches of the season (`rank_now`, where the match stands now; resets each season). Notification titles/openers use the as-of ranking (`rank.show`) the same way. A 10.0 is a "Perfect Game" (#n all-time), always shown; `perfect_games` on profiles. All-time stats never reset.
- Match page: box score above the team talk (passes made/att, key passes, assists, goals for every player in the match, rage quits tagged RQ with the minute). EA has no goal minutes, so no goal-time column.
- EA sometimes blanks a whole stat line (`stats_missing`): those performances get no stat-based coaching.

## Voice and content rules (from the user)
- All insights are written as Coach Lasso: warm, folksy, Ted Lasso-style framing, but every bullet tied to a real number and grounded in soccer coaching principles. No direct show quotes needed.
- Ratings are framed against the player's OWN games, never league percentages: `analysis.personal_rank` -> "3rd best match performance" / "2nd worst match performance" / "best match performance" (say match, not game; no counts); it sets the note title, the card chip and the opener tone. (Stat benchmarks like "top quarter hits 25+ passes" stay.)
- More Ted: every work bullet gets a lead-in and usually a tag-line (`WORK_TAIL`), and every note ends with a personal closing thought from Coach (`LASSOISMS` lines wrapped in `CLOSING_FRAMES`, addressed to the player by name). Never label them "Lasso-isms" - it should feel personal.
- Player notes: 6-10 bullets split between "did well" and "work on", personal to that player, one teammate line when it fits, a drill, signed "- Coach Lasso".
- Phrase pools were expanded ~5x (about 1,800 lines) in `fcapp/lasso_more.py` and `fcapp/daily_more.py`, merged append-only into `lasso.py`/`daily.py`. Add new variants there; every line must format with its pool's placeholders.
- Avoid repetition across everything a reader sees: `lasso.py` picks phrases least-recently-used club-wide, in match order. Add variants to the pools rather than reusing lines.
- Tapping a notification opens it in ntfy (no click URL); website only via the action buttons.

## Working on it
- The Desktop copy falls behind GitHub as the bot commits matches: `git pull --rebase` before editing, then push. Rebuild locally with `python -m fcapp.run --no-fetch --no-notify` (needs `pip install -r requirements.txt`).
- Commits end with a `Co-Authored-By` line when Claude makes them.
