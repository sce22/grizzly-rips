# FC 27 Pro Clubs Match Centre

A mobile website with your club's name, crest, and colours. It keeps every Pro Clubs match you play, breaks down each human player's performance, and texts you a link after each game.

```
EA Pro Clubs feed ──► watcher (checks every minute) ──► analysis ──► Coach ──► branded mobile site (GitHub Pages)
                                                                                  └─► team-talk text with link
```

## What it can and can't see

EA publishes a per-match report for every Pro Clubs game (the same data behind proclubs.ea.com). It lists **only human-controlled players**, so AI teammates and opponents never show up.

| Available per player, per match | Not in EA's feed |
|---|---|
| Match rating, position, minutes | Shot maps / shot locations |
| Goals, assists, shots, **shots on target*** | Heat maps / field positioning |
| Passes attempted / completed, **key passes*** | Crosses, dribbles, interceptions (itemised) |
| Tackles attempted / won (missed tackles) | Possession %, xG |
| Saves (by type), goals conceded, clean sheets | Event timeline |
| Red cards, Man of the Match, idle time | |

\* Decoded from EA's undocumented event counters. See `reference/ea-stats-reference.html` (the Stat Atlas) for every field and how each code was decoded.

**How players are graded.** Targets come from 4,764 real FC 27 performances by the top-40 clubs, split by position: top quarter counts as a strength and bottom quarter as a flag. Stats are also read in pairs, which catches forcing passes (below the ~72% break-even point), diving into tackles, shooting at the keeper, and a rating below what the stats predict (off-ball positioning). Each rating gets a badge relative to the position, because a 6.6 is a strong game for a keeper and a quiet one for a midfielder.

The site's "What moved the rating" section uses rating weights measured by regression on the same data (e.g. a forward's goal ≈ +0.61, a midfielder's tackle won ≈ +0.20, a keeper's goal conceded ≈ −0.41). Whatever the listed actions can't explain shows up as **Everything else**. The model retrains on the full archive after every match. Each position starts on those league weights and shifts toward your own games as they pile up (the baseline counts as 30 matches of evidence, `analysis.prior_matches`): about 25% yours after 10 matches, 50% after 30, 75% after 90. A snapshot of the current weights is saved to `data/model.json` each time, so you can watch it evolve. Position benchmarks ("top quarter of midfielders") stay league-wide on purpose so they keep meaning the same thing; comparisons to each player's own usual and all-time bests come from your archive.

**Important:** EA's feed only returns your last 10 matches per match type (a hard cap). The watcher checks every minute and files every match permanently by season in `data/seasons/season-NN/` (with a `summary.json` per season), so nothing is missed as long as GitHub Actions is running. Matches are never deleted: Coach Lasso's notes draw on a player's entire history (all-time bests, "first goal since Sep 29", streaks), and the site keeps every season browsable.

**Coach.** All insights are written by "Coach", a Ted Lasso-style voice grounded in the numbers and in standard soccer coaching principles (`fcapp/coach.py`, tips in `fcapp/playbook.py`). After every match, each player with a number on file gets their own short text in Coach's voice: score, their rating, what they did well, what to work on and one quick tip (plus a teammate nod when it fits). Email-to-text gateways cut messages at ~160 characters and drop follow-ups, so each text is one short paragraph capped at `notify.sms_max_chars` (125), plus a short link to your latest match. The full breakdown and team talk are on the site.

## One-time setup (~20 minutes)

### 1. Find your club ID
```bash
cd ~/Desktop/"FC Claude" && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```
```bash
.venv/bin/python -m fcapp.find_club "Your Club Name"
```
Use platform `common-gen5` for PS5 / Xbox Series / PC (the default).

### 2. Edit `config.json`
- `club.name`, `club.club_id`
- `club.logo`: `"auto"` uses your in-game crest. To use your own logo, put it in `branding/` (e.g. `branding/logo.png`) and set `"logo": "branding/logo.png"`
- `club.colors`: `"auto"` uses your kit colours. You can also set hex values, e.g. `"primary": "#0b2545"`
- `seasons`: a rolling schedule (first rollover, timezone, length in weeks) or a list of named date ranges
- `roster` (optional): list of gamertags to include; leave empty to include everyone on your side
- `site.base_url`: filled in after step 3

### 3. Put it on GitHub (free hosting, works on any phone)
1. Create a new GitHub repository (e.g. `fc-match-centre`) and push this folder to it.
2. Repo **Settings → Pages → Build and deployment → Deploy from a branch → `main` / `/docs`**.
3. Your site is `https://<username>.github.io/<repo>/`. Put that in `config.json → site.base_url`.
4. **Actions** tab → *Match watcher* → **Run workflow** to start it. After that GitHub restarts it on a schedule (a run lasts up to ~5.5 hours), and only one runs at a time. Skipped "pending" runs in the Actions list are normal.

> Free GitHub Pages sites are public. Only in-game stats are published; phone numbers stay in encrypted secrets.

### 4. Text messages
Add these under repo **Settings → Secrets and variables → Actions**:

**Option A – Twilio (reliable, ~$1/mo plus a small per-text fee)**
`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM` (your Twilio number), `NOTIFY_PHONE` (your number, `+15551234567`).
US numbers need Twilio's A2P 10DLC or toll-free verification before texts are delivered. It's a web form, and approval takes a few days.

**Option B – free email-to-text**
`SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER` (Gmail address), `SMTP_PASS` (a Gmail *app password*), `SMS_GATEWAY_ADDRESS` (e.g. `5551234567@vtext.com` for Verizon, `@tmomail.net` for T-Mobile). Carriers are phasing these gateways out, so delivery can be unreliable.

**Who gets texts:** your number (the `SMS_GATEWAY_ADDRESS` or `NOTIFY_PHONE` secret) gets the text for `notify.my_player` in `config.json`. To text teammates too, add a secret `PLAYER_SMS` = `{"GamerTag1": "5551234567@vtext.com", "GamerTag2": "+15551234567"}`.

The first sync saves existing matches without texting. After that you get one text per new match, usually 1-3 minutes after the final whistle. To check texting any time: **Actions → Send test text → Run workflow**.

### Push notifications (ntfy) - recommended
Free, instant, no carrier limits, and personal to each player.

- Every player who appears in our matches automatically gets a private ntfy channel, derived from the `NTFY_SECRET` repository secret. Channel names are never printed or committed.
- After each match, each player's channel gets **their own** notes from Coach Lasso: rating, 6-10 bullets split between what they did well and what to work on (each tied to a number), one drill, and a teammate line when it fits. Tapping it opens the full note in the ntfy app; the **My breakdown** and **Team talk** buttons open the website.
- **Adding someone:** they install the free **ntfy** app. You go to **Actions → Invite a player → Run workflow** (type their gamertag, or leave it blank for everyone). Their subscribe details arrive on *your* phone, ready to forward.
- **Testing:** **Actions → Send test message** (choose push, sms or all).
- Texts are off (`notify.sms: false`); push is on (`notify.push`). Flip either in `config.json`.

### League ladder
EA's public stats still report FC's old 10-division format, so the app tracks the FC 27 ladder itself (Division 5 up to Elite: a points phase with 3 lives - 7/9/12/14/18 pts - then promotion matches - win 1 of 3, 2 of 3, 3 of 4, 4 of 4, 5 of 5 (miss and it's back to 0 points); losing all 3 chances means a relegation match (win or draw: back where you left off; loss: down a division); Elite is unlimited) starting from a confirmed state, moving it forward after every league match. It shows on the Matches page and in each Daily Summary. If it ever disagrees with the game: **Actions -> Update league status** and enter what the game shows right now. That becomes the new starting point (as of the latest league match EA knows about), every later match moves it forward, the ladder history is kept, and the running watcher picks it up within a minute. The ladder lives on the Matches tab; it never sends notifications. Points targets per division live in `config.json` -> `league.rules`.

### Daily Summary (Coach Lasso's nightly pep talk)
- At 10:45pm CT, any day with 3+ matches (a day runs 10:45pm to 10:45pm) gets a 2-3 minute pep talk from Coach Lasso, a letter grade (A+ to F), key stats and the league ladder as it stood when the day closed (division, points phase or promotion matches, wins needed, lives left). It's pushed to everyone who played that day and saved forever under the **Daily** tab, with its own calendar.
- The mood follows the day: from a stern talking-to that finds its way back to hope, to full-blown celebration. An internal 0-20 scale (results, margins, ratings, and how the day compares to our normal) sets the tone and the grade; the number itself is never shown.
- Speeches are written by Claude when an `ANTHROPIC_API_KEY` repository secret is set (about 5 cents a night), otherwise by the built-in writer. Settings: `daily` and `league` in `config.json`.
- Test it: **Actions -> Send test message**, choose *daily summary*.

### If EA blocks GitHub's servers
EA sometimes blocks cloud servers. If the *Sync matches* run fails with `HTTP 403`, run the sync from your Mac instead (it only needs to be awake):
```bash
cp .env.example .env
```
Fill in `.env`, then:
```bash
./scripts/install_mac_sync.sh
```
The site still lives on GitHub Pages, so your phone link doesn't change.

## Preview with sample data
```bash
.venv/bin/python -m fcapp.demo && python3 -m http.server 8427 -d demo
```
Then open http://localhost:8427.

## Customising the coaching
All position targets, rating percentiles, interaction-rule thresholds and tips are in `fcapp/playbook.py`. The measured rating weights are in `fcapp/analysis.py` (`BASELINE`). Change them to match your club's style of play.

## Project layout
```
config.json           club identity, seasons, thresholds
fcapp/ea_client.py    EA Pro Clubs API client
fcapp/store.py        permanent match archive (data/matches/*.json)
fcapp/analysis.py     per-player grading, rating-impact model, themes
fcapp/playbook.py     position benchmarks + coaching tips
fcapp/build_site.py   builds the site into docs/
fcapp/notify.py       SMS via Twilio or email gateway
fcapp/run.py          the pipeline (fetch → analyse → build → text)
site/                 mobile web app template
.github/workflows/    20-minute scheduled sync
```
