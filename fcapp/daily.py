"""Nightly Daily Summary: Coach Lasso's pep talk, a grade, key stats and where
we stand in the league table.

A "day" runs from 10:45pm CT the previous night to 10:45pm CT (the send time),
so late-night matches roll into the next day's summary. A summary is written
only for days with at least `daily.min_games` matches, and goes to everyone
who played that day. Each summary is saved for good in data/daily/<date>.json.

The speech is written by Claude when ANTHROPIC_API_KEY is set; otherwise (or
if the call fails) a built-in Lasso-style writer produces it. Either way it is
generated once, when the day closes, and never rewritten.
"""
import json
import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from . import playbook as pb
from .lasso import COACH, Picker, Rotation, _an
from .store import DATA

DAILY_DIR = DATA / "daily"
GRADES = ["F", "D-", "D", "D+", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+"]


# ------------------------------------------------------------------ the day

def settings(config):
    d = config.get("daily", {})
    return {
        "tz": ZoneInfo(d.get("timezone", "America/Chicago")),
        "send_at": time.fromisoformat(d.get("send_at", "22:45")),
        "min_games": d.get("min_games", 3),
        "start_date": d.get("start_date", "1970-01-01"),
        "season_games": config.get("league", {}).get("season_games", 10),
    }


def day_of(ts, cfg):
    """Summary date a match belongs to (matches after the send time roll forward)."""
    local = datetime.fromtimestamp(ts, cfg["tz"])
    return (local.date() + timedelta(days=1)) if local.time() >= cfg["send_at"] else local.date()


def window(day, cfg):
    end = datetime.combine(day, cfg["send_at"], cfg["tz"])
    return end - timedelta(days=1), end


def path_for(day):
    return DAILY_DIR / f"{day.isoformat()}.json"


def load_all():
    if not DAILY_DIR.exists():
        return []
    return sorted((json.loads(p.read_text()) for p in DAILY_DIR.glob("*.json")), key=lambda d: d["date"])


def score_day(day_matches, club_ppg):
    """Internal 0-20 mood scale (never shown) from results, margins and form vs normal."""
    n = len(day_matches)
    pts = sum({"W": 3, "D": 1, "L": 0}[m["result"]] for m in day_matches)
    ppg = pts / n
    gd = sum(m["gf"] - m["ga"] for m in day_matches) / n
    ratings = [p["stats"]["rating"] for m in day_matches for p in m["players"]]
    avg_rating = sum(ratings) / len(ratings) if ratings else 7.0
    s = ppg / 3 * 13                                   # results drive most of it (0-13)
    s += (max(-3.0, min(3.0, gd)) + 3) / 6 * 4         # how convincing (0-4)
    s += max(0.0, min(1.5, (avg_rating - 6.5)))        # how well we played (0-1.5)
    if club_ppg is not None:                           # better or worse than our normal (+/-2)
        s += max(-2.0, min(2.0, (ppg - club_ppg) * 2))
    return max(0, min(20, round(s)))


def grade_for(score):
    return GRADES[round(score / 20 * (len(GRADES) - 1))]


TONE = [  # (max score, guidance) - drives both Claude and the built-in writer
    (3, "Deeply disappointed. Open with honest, firm scolding about what went wrong, name it plainly, then build a long, sincere through-line to hope by the end."),
    (6, "Frustrated but fatherly. Tough love first, specific about the problems, then turn the corner into steady optimism."),
    (9, "Mixed day, slightly below par. Measured and honest, credit what worked, challenge what didn't, end encouraged."),
    (12, "Solid, mixed-to-good day. Warm and proud with clear notes for improvement."),
    (15, "Good day. Proud and upbeat, celebrate specifics, still one or two coaching notes."),
    (18, "Great day. Jubilant, big praise, playful, hype them up with a light coaching touch."),
    (20, "Phenomenal day. Maximum hype, over-the-top joy and celebration, the full Lasso fireworks."),
]


def tone_for(score):
    return next(t for cap, t in TONE if score <= cap)


# ------------------------------------------------------------ league table

def standing(client, club_id, club_name, season_games):
    """Where we stand right now in EA's league: division, this season's results
    and the points we need. EA only reports the current moment, so each daily
    summary stores the snapshot taken when it was written."""
    stats = (client._get("clubs/overallStats", clubIds=club_id) or [{}])[0]
    search = client._get("allTimeLeaderboard/search", clubName=club_name) or []
    me = next((c for c in search if str(c.get("clubId")) == str(club_id)), {})
    division = int(me.get("currentDivision") or 0) or None
    thresholds = (client._get("settings") or {}).get(str(division), {}) if division else {}
    codes = [int(stats.get(f"lastMatch{i}", -1)) for i in range(season_games)]
    played = [c for c in codes if c != -1]
    w, l, d = played.count(1), played.count(2), played.count(3)
    pts = 3 * w + d
    remaining = season_games - len(played)
    out = {
        "division": division, "division_name": thresholds.get("divisionName") or (f"Division {division}" if division else None),
        "season_games": season_games, "played": len(played), "remaining": remaining,
        "record": {"W": w, "D": d, "L": l}, "points": pts, "max_points": pts + 3 * remaining,
        "results": ["W" if c == 1 else "L" if c == 2 else "D" for c in reversed(played)],  # oldest first
        "hold": thresholds.get("pointsToHoldDivision"), "promotion": thresholds.get("pointsForPromotion"),
        "title": thresholds.get("pointsToTitle"),
        "promotions": int(stats.get("promotions") or 0), "relegations": int(stats.get("relegations") or 0),
        "skill_rating": int(stats.get("skillRating") or 0) or None,
        "playoff_games": int(stats.get("gamesPlayedPlayoff") or 0),
        "taken_at": datetime.now(ZoneInfo("America/Chicago")).isoformat(timespec="minutes"),
    }
    out["status"] = table_status(out)
    return out


def _need(target, pts, remaining):
    """(points still needed, wins needed, reachable?)"""
    gap = max(0, target - pts)
    return gap, -(-gap // 3), gap <= 3 * remaining


def table_status(t):
    """Plain-English lines about promotion, title and relegation."""
    lines, pts, rem = [], t["points"], t["remaining"]
    if t.get("promotion") is not None:
        gap, wins, ok = _need(t["promotion"], pts, rem)
        if gap == 0:
            lines.append(f"Promotion secured ({pts}/{t['promotion']} pts)")
        elif ok:
            lines.append(f"Promotion: {gap} more pts needed ({t['promotion']} total), about {_plural(wins, 'win')} from {_plural(rem, 'game')} left")
        else:
            lines.append(f"Promotion out of reach this season ({t['promotion']} pts needed, max possible {t['max_points']})")
    if t.get("title") is not None:
        gap, wins, ok = _need(t["title"], pts, rem)
        if gap == 0:
            lines.append(f"Division title clinched ({t['title']} pts)")
        elif ok:
            lines.append(f"Title: {gap} more pts for the title ({t['title']} total)")
    if t.get("hold") is not None and t["hold"] >= 0:
        gap, wins, ok = _need(t["hold"], pts, rem)
        if gap == 0:
            lines.append(f"Safe from relegation ({pts}/{t['hold']} pts)")
        elif ok:
            lines.append(f"Safety: {gap} more pts to stay up ({t['hold']} total) with {_plural(rem, 'chance')} left")
        else:
            lines.append(f"Relegation can't be avoided this season ({t['hold']} pts needed)")
    elif t.get("hold") == -1:
        lines.append("No relegation from this division")
    if t["playoff_games"]:
        lines.append(f"Playoff matches played: {t['playoff_games']}")
    return lines


def _plural(n, word, plural=None):
    return f"{n} {word if n == 1 else (plural or word + 's')}"


# ------------------------------------------------------------ the summary

def summarize_players(day_matches):
    agg = {}
    for m in day_matches:
        for p in m["players"]:
            a = agg.setdefault(p["name"], {"name": p["name"], "games": 0, "goals": 0, "assists": 0, "key_passes": 0,
                                           "tackles_won": 0, "ratings": [], "mom": 0, "pos": p["pos"], "tags": {}})
            s = p["stats"]
            a["games"] += 1
            a["goals"] += s["goals"]
            a["assists"] += s["assists"]
            a["key_passes"] += s.get("key_passes") or 0
            a["tackles_won"] += s["tackles_made"]
            a["ratings"].append(s["rating"])
            a["mom"] += s["mom"]
            for w in p["weaknesses"]:
                a["tags"][w["tag"]] = a["tags"].get(w["tag"], 0) + 1
    out = []
    for a in agg.values():
        a["avg_rating"] = round(sum(a["ratings"]) / len(a["ratings"]), 2)
        a["best_rating"] = max(a["ratings"])
        a["top_issue"] = max(a["tags"], key=a["tags"].get) if a["tags"] else None
        del a["ratings"], a["tags"]
        out.append(a)
    return sorted(out, key=lambda a: -a["avg_rating"])


def build(day, matches, cfg, table=None, rotation=None):
    """Build the summary data (everything except the speech)."""
    start, end = window(day, cfg)
    dm = [m for m in matches if start.timestamp() <= m["ts"] < end.timestamp()]
    before = [m for m in matches if m["ts"] < start.timestamp()]
    club_ppg = (sum({"W": 3, "D": 1, "L": 0}[m["result"]] for m in before) / len(before)) if len(before) >= 5 else None
    rec = {"W": 0, "D": 0, "L": 0}
    for m in dm:
        rec[m["result"]] += 1
    score = score_day(dm, club_ppg)
    players = summarize_players(dm)
    best = max(dm, key=lambda m: (m["gf"] - m["ga"], m["gf"]))
    worst = min(dm, key=lambda m: (m["gf"] - m["ga"], m["gf"]))
    issues = {}
    for m in dm:
        for p in m["players"]:
            for w in p["weaknesses"]:
                issues[w["tag"]] = issues.get(w["tag"], 0) + 1
    team_issue = max(issues, key=issues.get) if issues else None
    return {
        "date": day.isoformat(),
        "label": f"{day:%a, %b} {day.day}",
        "title": f"{day:%b} {day.day} Daily Summary",
        "games": len(dm), "record": rec, "gf": sum(m["gf"] for m in dm), "ga": sum(m["ga"] for m in dm),
        "points": 3 * rec["W"] + rec["D"], "club_ppg_before": round(club_ppg, 2) if club_ppg is not None else None,
        "score": score, "grade": grade_for(score),
        "players": players, "active": [p["name"] for p in players],
        "mvp": players[0]["name"] if players else None,
        "best_match": {"id": best["id"], "score": f"{best['gf']}-{best['ga']}", "opp": best["opponent"]["name"], "result": best["result"]},
        "worst_match": {"id": worst["id"], "score": f"{worst['gf']}-{worst['ga']}", "opp": worst["opponent"]["name"], "result": worst["result"]},
        "team_issue": team_issue,
        "matches": [{"id": m["id"], "ts": m["ts"], "result": m["result"], "gf": m["gf"], "ga": m["ga"], "opp": m["opponent"]["name"]} for m in dm],
        "table": table,
    }


def key_stats(s):
    """Short stat lines shown under the speech (notification and site)."""
    r = s["record"]
    lines = [f"Day: {r['W']}W {r['D']}D {r['L']}L from {_plural(s['games'], 'match', 'matches')} · {s['gf']} scored, {s['ga']} conceded"]
    if s["mvp"]:
        p = s["players"][0]
        lines.append(f"Player of the day: {p['name']} ({p['avg_rating']:.1f} avg, {_plural(p['goals'], 'goal')}, {_plural(p['assists'], 'assist')})")
    t = s.get("table")
    if t and t.get("division"):
        lines.append(f"Table: {t['division_name']} · {t['points']} pts after {t['played']}/{t['season_games']} games ({t['record']['W']}W {t['record']['D']}D {t['record']['L']}L)")
        lines += t["status"]
        lines.append(f"Games left this season: {t['remaining']}")
    return lines


# ------------------------------------------------------- the speech: Claude

SYSTEM_PROMPT = """You write a post-game pep talk transcript for a Pro Clubs team in EA Sports FC 27, in the voice of a coach modeled on Ted Lasso: folksy Midwestern warmth, relentless belief in people, homespun metaphors, gentle humor, sincere, never mean-spirited even when stern. Use original lines; do not quote the TV show.

The coach is speaking directly to the players after their day of matches. It is a spoken speech transcript: plain paragraphs, no headings, no bullet points, no markdown, no stage directions. Length: 330 to 430 words (about 2 to 3 minutes spoken).

Be specific and informative: mention the actual results, scores, opponents and named players with their real numbers, the main thing to fix next time with a concrete soccer coaching point, and where the team stands in the league if table data is given. Do not invent statistics that aren't in the data.

Match the emotional register given in the tone guidance exactly. Never mention a numeric score, scale, grade or rating out of anything for the day."""


def claude_speech(summary, tone):
    """Write the speech with Claude. Returns None if no key or on any failure."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None
    facts = {k: summary[k] for k in ("label", "games", "record", "gf", "ga", "players", "best_match", "worst_match", "matches")}
    facts["club_name"] = summary.get("club")
    facts["main_team_issue"] = pb.TAG_TITLES.get(summary["team_issue"]) if summary.get("team_issue") else None
    facts["coaching_points_for_that_issue"] = pb.tips_for(summary["team_issue"], "_", 4) if summary.get("team_issue") else []
    facts["league_table"] = {"division": summary["table"]["division_name"], "points": summary["table"]["points"],
                             "played": summary["table"]["played"], "remaining": summary["table"]["remaining"],
                             "status": summary["table"]["status"]} if summary.get("table") else None
    try:
        client = anthropic.Anthropic()
        response = client.beta.messages.create(
            model="claude-opus-5-5",
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            extra_body={"fallbacks": "default"},  # re-run on Anthropic's recommended model if declined
            output_config={"effort": "medium"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content":
                       f"Tone guidance for today: {tone}\n\nToday's data (JSON):\n{json.dumps(facts, indent=1)}\n\nWrite the speech."}],
        )
    except anthropic.APIConnectionError:
        print("[daily] Claude unreachable - using the built-in writer")
        return None
    except anthropic.RateLimitError:
        print("[daily] Claude rate limited - using the built-in writer")
        return None
    except anthropic.APIStatusError as e:
        print(f"[daily] Claude error {e.status_code} - using the built-in writer")
        return None
    if response.stop_reason == "refusal":
        print("[daily] Claude declined - using the built-in writer")
        return None
    text = "\n\n".join(b.text.strip() for b in response.content if b.type == "text").strip()
    return text if len(text.split()) >= 200 else None


# ------------------------------------------------ the speech: built-in writer

OPEN = {
    "low": ["Alright, bring it in. Sit down, all of you. No, the floor is fine. I want us all at eye level for this one.",
            "Y'all, I'm gonna be straight with you, because that's what you deserve: today was not it.",
            "Okay. Deep breath. Everybody take one with me. In through the nose. Out through the disappointment."],
    "mid": ["Gather round, gather round. Grab a water, grab a seat, grab a teammate's shoulder if you need it.",
            "Well, that was a day, wasn't it? A real choose-your-own-adventure kind of day.",
            "Alright, team. Today was a little like my first attempt at a soufflé: parts of it rose, parts of it didn't."],
    "high": ["Get in here! Everybody! Bring it in so close I can smell the effort on you!",
             "Oh, I have been waiting all day to give this speech. All. Day.",
             "Somebody pinch me, because I think I just watched the best version of this team so far."],
}
RECAP = ["We played {games} today. {W} {W_w}, {D} {D_w}, {L} {L_w}. We put {gf} in the back of the net and let {ga} into ours.",
         "{games} matches. {W} {W_w}, {D} {D_w}, {L} {L_w}. {gf} goals for, {ga} against. Those are the facts, and facts are friends, even the grumpy ones.",
         "Let's do the arithmetic first, because math doesn't have feelings: {games} games, {W} {W_w}, {D} {D_w}, {L} {L_w}, {gf} scored and {ga} conceded."]
BEST = ["The high point? That {score} against {opp}. That one I'm gonna play on loop in my head while I brush my teeth.",
        "When it clicked, it really clicked. Look at the {score} over {opp}. That's who we can be.",
        "And that {score} against {opp}? That was football the way grandma makes pie: all the right ingredients, and plenty of love."]
WORST = ["Now, the {score} against {opp}. I'm not gonna pretend that one didn't sting, because it stung like a bee with something to prove.",
         "We also have to talk about {opp}. {score}. That one's sitting in my stomach like a gas-station burrito.",
         "The {score} against {opp} is the one we learn the most from, and lessons are only expensive if we waste 'em."]
CORE = {
    "low": ["I'm disappointed, and I'm not gonna hide it. Not in you as people. You're good people. I'm disappointed because I've seen what you can do, and today we left a lot of it in the locker room. We were second to loose balls, we got sloppy with the ball, and when it went wrong we stopped talking to each other.",
            "Here's the honest truth: we beat ourselves more than they beat us. Passes we didn't need to force. Tackles we dove into. Runners we didn't track. Little leaks, and little leaks sink big boats.",
            "And I need you to hear this part: losing happens. Losing the way we lost, where heads drop and voices go quiet, that's the part I won't accept. Football's a team sport even when it's going badly. Especially when it's going badly.",
            "We stopped doing the simple things. Simple passes, simple runs, simple talking. When the simple stuff goes, the fancy stuff never shows up to replace it."],
    "mid": ["It wasn't a bad day, and it wasn't a great one. It was a 'we're figuring it out' day, and I'll take a figuring-it-out day over a giving-up day every single time.",
            "There were stretches out there where we looked like a real team, and stretches where we looked like eleven strangers at a bus stop. The goal is more of the first one.",
            "When we kept it simple and talked to each other, we were tough to beat. When we tried to win it all with one pass, we gave it right back. That's not a talent problem. That's a patience problem, and patience is learnable.",
            "Nobody's hanging their head tonight. We had our moments, we had our mistakes, and both of 'em are information. Good coaches love information almost as much as biscuits."],
    "high": ["What I saw today was a team that trusts each other. You played for the person next to you, and that's the whole secret. That's it. That's the speech. Well, no, I've got more.",
             "You moved the ball like it was hot, you closed down like you meant it, and when one of us made a mistake somebody else covered without a word. That's chemistry, and you can't buy it at any store I've been to.",
             "Every time they thought they had an answer, you asked a new question. That's what good teams do, and tonight you were a good team. Heck, you were a great one.",
             "I want you to remember how this felt. Not the scoreline, the feeling. The way you looked for each other, the way you celebrated each other. That feeling is the whole reason we do this."],
}
STORY = {
    "low": ["My daddy used to say a rough day is just a good day that got lost on the way home. It still knows the address. We just gotta go pick it up.",
            "You know, they say the oak tree that survives the storm is the one with the deepest roots. Today was a storm. Tomorrow we find out how deep our roots go."],
    "mid": ["Back home there's a diner that burns the first pancake every single morning, on purpose. Says it seasons the pan. Today might've been our first pancake.",
            "A garden doesn't grow in one afternoon. You water it, you pull a few weeds, and one day you look up and you've got tomatoes. We're in the watering part."],
    "high": ["I once saw a kid at a county fair win the ring toss five times in a row, and the whole crowd just started chanting his name. That's how I felt watching you tonight. I was the crowd. I was chanting.",
             "My mama always said when the cornbread comes out golden, you don't ask why, you just pass the butter. Pass the butter, y'all."],
}
FOCUS = ["Now, the one thing we fix before next time: {issue}. {tip}",
         "If we work on one thing, let it be {issue}. Here's how: {tip}",
         "Homework, and yes, I'm assigning homework: {issue}. {tip}"]
TABLE = ["Where does that leave us? We're in {div} with {pts} points from {played} games this season, {rem} left to play. {status}.",
         "A word on the table, because the table never lies: {div}, {pts} points, {played} played, {rem} to go. {status}.",
         "League check: {pts} points in {div} with {rem} games remaining. {status}."]
CLOSE = {
    "low": ["So tonight, be a goldfish about the scoreline. Tomorrow, we come back and we fix it together. I still believe in this team. Heck, I believe in it more after a day like this, because I know how bad you want it.",
            "I'm not giving up on this group, so you don't get to either. Go home, rest up, and come back hungry. We're gonna be alright. Better than alright."],
    "mid": ["Proud of the fight, hungry for more. Get some sleep, drink some water, and let's go turn a figuring-it-out day into a figured-it-out week.",
            "We're closer than the scoreboard says. Rest up. Tomorrow we take another swing, and I like our odds."],
    "high": ["Now go home, call somebody who loves you, and tell 'em about today. And then rest, because tomorrow we do it again, and I want you just as hungry as you were tonight. Believe!",
             "I'm so proud of you I could burst like a water balloon at a church picnic. Enjoy it tonight. Every single one of you earned it."],
}


TEAMWORK = {
    "low": ["One bright spot: {a} and {b} kept finding each other, {n} goals between 'em. Build from that partnership, and build out.",
            "Even on a day like this, {a} and {b} combined for {n} goals. That tells me the bones are good. We just gotta put the meat back on 'em."],
    "mid": ["{a} and {b} combined for {n} goals today. When those two connect, everybody else gets more room. Let's feed that.",
            "I loved watching {a} and {b} link up, {n} goals between 'em. Partnerships like that are the backbone of a team."],
    "high": ["{a} and {b}, {n} goals between you. You two were like peanut butter and jelly, and the rest of the team was the bread holding it all together.",
             "And can we talk about {a} and {b}? {n} goals between 'em. If that partnership were a band, I'd buy the t-shirt."],
}
RALLY = {
    "low": ["Here's what I know about this group. You care. I can see it on your faces right now. And people who care this much don't stay down for long.",
            "Tomorrow isn't a do-over. It's a do-better. And doing better starts with the first pass, the first tackle, the first time you call for the ball."],
    "mid": ["We're not far off. We're a couple of good decisions a match from turning draws into wins and losses into draws. That's a short walk, y'all.",
            "I'd rather coach a team that's figuring it out than one that thinks it already has. Stay hungry, stay humble, stay together."],
    "high": ["Days like this don't happen by accident. They happen because you showed up for each other, every touch, every run, every shout.",
             "Now, I'm not gonna tell you to come back down to earth. You can float a little tonight. You earned the altitude."],
}


def _mood(score):
    return "low" if score <= 6 else "mid" if score <= 12 else "high"


def player_line(p, mood, pick):
    if p["goals"] or p["avg_rating"] >= 7.8:
        bits = []
        if p["goals"]:
            bits.append(_plural(p["goals"], "goal"))
        if p["assists"]:
            bits.append(_plural(p["assists"], "assist"))
        if p["key_passes"]:
            bits.append(_plural(p["key_passes"], "key pass", "key passes"))
        return pick("dp_good", [
            "{name}, {bits} across {games} and a {r} average. That's the kind of day that makes a coach misty.",
            "{name}: {bits}, {r} average. You were the steady heartbeat of this team today.",
            "And {name}, {bits} and a {r} average over {games}. Don't you dare let anybody tell you that didn't matter.",
        ]).format(name=p["name"], bits=", ".join(bits) or "solid work", games=_plural(p["games"], "game"), r=f"{p['avg_rating']:.1f}")
    issue = pb.TAG_TITLES.get(p["top_issue"], "the little things").lower() if p["top_issue"] else "the little things"
    return pick("dp_work", [
        "{name}, {r} average over {games}. I know there's more in there. Let's start with {issue}.",
        "{name}, you battled, {r} average, and I want us to sharpen {issue} together this week.",
        "{name}, {games} and a {r} average. Not your night, but nights don't define players. Habits do. Ours starts with {issue}.",
    ]).format(name=p["name"], r=f"{p['avg_rating']:.1f}", games=_plural(p["games"], "game"), issue=issue)


def builtin_speech(s, rotation):
    """Returns (speech, phrase ids used) so later days rotate away from them."""
    pick = Picker(f"daily|{s['date']}", rotation)
    mood = _mood(s["score"])
    r = s["record"]
    word = lambda n, one, many: one if n == 1 else many
    paras = [pick("d_open_" + mood, OPEN[mood]),
             pick("d_recap", RECAP).format(games=s["games"], W=r["W"], D=r["D"], L=r["L"], gf=s["gf"], ga=s["ga"],
                                           W_w=word(r["W"], "win", "wins"), D_w=word(r["D"], "draw", "draws"), L_w=word(r["L"], "loss", "losses"))]
    moments = []
    if s["best_match"]["result"] == "W":
        moments.append(pick("d_best", BEST).format(**s["best_match"]))
    if s["worst_match"]["result"] == "L":
        moments.append(pick("d_worst", WORST).format(**s["worst_match"]))
    paras.append(" ".join(moments + [pick("d_core_" + mood, CORE[mood])]))
    paras.append(pick("d_core_" + mood, CORE[mood]))  # a second, different beat
    paras.append(" ".join(player_line(p, mood, pick) for p in s["players"]))
    pair = sorted(s["players"], key=lambda p: -(p["goals"] + p["assists"]))[:2]
    if len(pair) == 2 and pair[0]["goals"] + pair[1]["goals"] >= 2:
        paras.append(pick("d_team_" + mood, TEAMWORK[mood]).format(a=pair[0]["name"], b=pair[1]["name"], n=pair[0]["goals"] + pair[1]["goals"]))
    paras.append(pick("d_story_" + mood, STORY[mood]))
    if s["team_issue"]:
        tips = pb.tips_for(s["team_issue"], "_", 12)
        paras.append(pick("d_focus", FOCUS).format(issue=pb.TAG_TITLES[s["team_issue"]].lower(), tip=pick("t_" + s["team_issue"], tips)))
    t = s.get("table")
    if t and t.get("division") and t["status"]:
        paras.append(pick("d_table", TABLE).format(div=t["division_name"], pts=t["points"], played=t["played"],
                                                   rem=t["remaining"], status=t["status"][0]))
    paras.append(pick("d_rally_" + mood, RALLY[mood]))
    paras.append(pick("d_close_" + mood, CLOSE[mood]))
    return _an("\n\n".join(paras)), sorted(pick.used)


# ---------------------------------------------------------------- running it

def past_rotation():
    """Rebuild the phrase rotation from every saved summary, oldest first."""
    rot = Rotation()
    for old in load_all():
        for key in old.get("phrases", []):
            rot.seq += 1
            rot.last[key] = rot.seq
    return rot


def generate(day, matches, config, table=None, rotation=None):
    cfg = settings(config)
    s = build(day, matches, cfg, table)
    s["club"] = config["club"]["name"]
    tone = tone_for(s["score"])
    speech = claude_speech(s, tone)
    s["speech_by"] = "claude" if speech else "builtin"
    if speech:
        s["speech"], s["phrases"] = speech, []
    else:
        s["speech"], s["phrases"] = builtin_speech(s, rotation or past_rotation())
    s["key_stats"] = key_stats(s)
    s["coach"] = COACH
    s["generated_at"] = datetime.now(cfg["tz"]).isoformat(timespec="minutes")
    return s


def due_days(matches, config, now=None):
    """Closed days with enough games that have no summary yet (oldest first)."""
    cfg = settings(config)
    now = now or datetime.now(cfg["tz"])
    by_day = {}
    for m in matches:
        by_day.setdefault(day_of(m["ts"], cfg), []).append(m)
    out = []
    for day, ms in sorted(by_day.items()):
        closed = window(day, cfg)[1] <= now
        if closed and len(ms) >= cfg["min_games"] and not path_for(day).exists():
            out.append(day)
    return out


def save(summary):
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    path_for(datetime.fromisoformat(summary["date"]).date()).write_text(json.dumps(summary, indent=1, ensure_ascii=False))


def should_notify(summary, config, now=None):
    """Only tonight's summary is pushed, and only once nightly sends have started."""
    cfg = settings(config)
    now = now or datetime.now(cfg["tz"])
    end = window(datetime.fromisoformat(summary["date"]).date(), cfg)[1]
    return summary["date"] >= cfg["start_date"] and now - end < timedelta(hours=6)


def notification(summary, base_url):
    """(title, body, url) for the push. ntfy turns messages over 4 KB into
    attachments, so the speech is trimmed at a paragraph if it ever gets close."""
    url = f"{base_url}#/daily/{summary['date']}"
    title = f"{summary['title']} · Coach Lasso's grade: {summary['grade']}"
    stats = "\n".join(f"• {line}" for line in summary["key_stats"])
    tail = f"\n\n- {summary['coach']}\n\nKEY STATS\n{stats}"
    paras = summary["speech"].split("\n\n")
    while len(("\n\n".join(paras) + tail).encode()) > 3800 and len(paras) > 2:
        paras.pop(-2)
    return title, "\n\n".join(paras) + tail, url
