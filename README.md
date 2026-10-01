# FC 27 Pro Clubs Match Centre

A mobile website with your club's name, crest, and colours. It keeps every Pro Clubs match you play, breaks down each human player's performance, and texts you a link after each game.

```
EA Pro Clubs feed ──► collector (every 20 min) ──► analysis ──► branded mobile site (GitHub Pages)
                                                             └─► text message with link
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

The site's "What moved the rating" section uses rating weights measured by regression on the same data (e.g. a forward's goal ≈ +0.61, a midfielder's tackle won ≈ +0.20, a keeper's goal conceded ≈ −0.41). Whatever the listed actions can't explain shows up as **Everything else**. Once your club has 40+ player-matches per position, the weights are re-learned from your own games.

**Important:** EA's feed only returns your last ~10 matches per match type. The archive grows because the sync runs every 20 minutes and saves every match permanently. If the sync stops for a long stretch, matches played in that gap are lost.

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
4. **Actions** tab → *Sync matches* → **Run workflow** to do the first sync. After that it runs by itself every 20 minutes.

> Free GitHub Pages sites are public. Only in-game stats are published; phone numbers stay in encrypted secrets.

### 4. Text messages
Add these under repo **Settings → Secrets and variables → Actions**:

**Option A – Twilio (reliable, ~$1/mo plus a small per-text fee)**
`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM` (your Twilio number), `NOTIFY_PHONE` (your number, `+15551234567`).
US numbers need Twilio's A2P 10DLC or toll-free verification before texts are delivered. It's a web form, and approval takes a few days.

**Option B – free email-to-text**
`SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER` (Gmail address), `SMTP_PASS` (a Gmail *app password*), `SMS_GATEWAY_ADDRESS` (e.g. `5551234567@vtext.com` for Verizon, `@tmomail.net` for T-Mobile). Carriers are phasing these gateways out, so delivery can be unreliable.

**Per-player texts (optional):** set `notify.per_player_texts: true` and add a secret `PLAYER_PHONES` = `{"GamerTag1": "+1555...", "GamerTag2": "+1555..."}`. Each of those players gets a link straight to their own breakdown.

The first sync saves existing matches without texting. After that you get one text per new match.

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
