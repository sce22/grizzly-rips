"""Nightly Daily Summary: Coach Lasso's pep talk, a grade, key stats and where
we stand in the league table.

A "day" runs from 11pm CT the previous night to 11pm CT (the send time),
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
        "send_at": time.fromisoformat(d.get("send_at", "23:00")),
        "min_games": d.get("min_games", 3),
        "start_date": d.get("start_date", "1970-01-01"),
        "hold": set(d.get("hold", [])),  # dates not to write yet (e.g. while the writer is being upgraded)
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


BASELINE_MIN = 20     # matches before the team baseline starts to count
BASELINE_PRIOR = 40   # the league-standard scale counts like this many matches


def _day_stats(ms):
    n = len(ms)
    ratings = [p["stats"]["rating"] for m in ms for p in m["players"]]
    return {"ppg": sum({"W": 3, "D": 1, "L": 0}[m["result"]] for m in ms) / n,
            "gd": sum(m["gf"] - m["ga"] for m in ms) / n,
            "rating": sum(ratings) / len(ratings) if ratings else 7.0}


def team_baseline(before):
    """Our own normal from every match before the day. It phases in once we
    have BASELINE_MIN matches and weighs more as the sample grows:
    weight = n / (n + BASELINE_PRIOR) - about a third at 20 matches, half at
    40, two thirds at 80."""
    n = len(before)
    if n < BASELINE_MIN:
        return {"matches": n, "weight": 0.0}
    b = _day_stats(before)
    return {"matches": n, "weight": round(n / (n + BASELINE_PRIOR), 2),
            "ppg": round(b["ppg"], 2), "gd": round(b["gd"], 2), "rating": round(b["rating"], 2)}


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def score_day(day_matches, baseline, story=None):
    """Internal 0-20 scale (never shown; 10 = an ordinary day).

    Results, goal margin and ratings are judged two ways and blended by how
    much of our own history we have:
      * league standard - a fixed scale (1.5 pts per match, level goals and a
        6.8 average rating is a 10)
      * our baseline - the same three things against this team's own usual
    Then the ladder and conduct apply on top, whatever the blend: dropping a
    division, burning our last chance, a failed promotion or rage quits cost
    marks; promotions and survived relegation matches earn them.
    """
    d = _day_stats(day_matches)
    standard = 10 + (d["ppg"] - 1.5) * 5 + _clamp(d["gd"], -3, 3) * 1.5 + _clamp(d["rating"] - 6.8, -1.5, 1.5) * 2
    w = baseline.get("weight", 0.0)
    base = standard
    if w:
        relative = (10 + (d["ppg"] - baseline["ppg"]) * 6 + _clamp(d["gd"] - baseline["gd"], -3, 3) * 1.2
                    + _clamp(d["rating"] - baseline["rating"], -1.5, 1.5) * 2)
        base = (1 - w) * standard + w * relative
    return round(_clamp(base + ladder_and_conduct(day_matches, story), 0, 20))


def ladder_and_conduct(day_matches, story):
    adj = 0.0
    if story:
        adj += {"down": -4.0, "up": 3.0}.get(story.get("moved"), 0.0)
        if story.get("facing_relegation") and story["start"] and story["start"]["stage"] != "relegation":
            adj -= 1.5
        kinds = [e["kind"] for e in story.get("events", [])]
        adj += -1.0 * kinds.count("promotion_failed") + 1.5 * kinds.count("qualified") + 1.0 * kinds.count("survived")
    quits = sum(1 for m in day_matches for p in m["players"] if p["stats"].get("rage_quit"))
    return adj - min(3, quits)


def grade_for(score):
    return GRADES[round(score / 20 * (len(GRADES) - 1))]


TONE = [  # (max score, guidance) - drives both Claude and the built-in writer
    (2, "SCATHING. This was a disaster and the speech has to say so. Open by absolutely laying into the team: blunt, loud, specific, "
        "naming the worst results, the goals conceded, any relegation or burned chances, and rage quits. Then go round the room and give "
        "EVERY player 2-3 explicit, number-backed things they did badly (still credit a genuine bright spot if one exists). Only in the "
        "last third does Coach soften: in classic Ted Lasso style he turns it around with warmth, belief and a homespun story, and ends "
        "on a genuinely high, hopeful note about tomorrow."),
    (5, "Furious-but-fatherly. Lead with hard, honest criticism of the day and specific failures, call out every player's 2-3 worst "
        "habits with numbers while noting real positives, then turn the corner into belief and finish on a high note."),
    (8, "Below par. Honest and firm: name what went wrong and who needs to sharpen what, credit what worked, end encouraged and upbeat."),
    (11, "An ordinary day. Measured and warm: credit what worked, challenge what didn't, end with optimism."),
    (14, "Good day. Proud and upbeat, celebrate specifics, still one or two coaching notes, finish buzzing."),
    (17, "Great day. Jubilant, big praise, playful, hype them up with a light coaching touch."),
    (20, "Phenomenal day. Maximum hype, over-the-top joy and celebration, the full Lasso fireworks."),
]


def tone_for(score):
    return next(t for cap, t in TONE if score <= cap)


# ------------------------------------------------------------ league table
# The ladder (division, points phase, promotion/relegation matches) comes from
# fcapp/league.py; EA's own division fields still use FC's old format.


def _plural(n, word, plural=None):
    return f"{n} {word if n == 1 else (plural or word + 's')}"


# ------------------------------------------------------------ the summary

FAMILY_OF = None


def _family(metric):
    from .lasso import FAMILY
    return FAMILY.get(metric, metric)


def _pct_of(made, att):
    return round(made / att * 100) if att else None


def summarize_players(day_matches, before):
    """Each player's day: numbers, how it compares with their own usual, and
    the strongest good / bad / ugly signals from their matches (one per stat
    family, so the 2-3 lowlights are different problems)."""
    usual = {}
    for m in before:
        for p in m["players"]:
            if not p["stats"].get("rage_quit") and not p["stats"].get("stats_missing"):
                usual.setdefault(p["name"], []).append(p["stats"])
    agg = {}
    for i, m in enumerate(day_matches, 1):
        for p in m["players"]:
            a = agg.setdefault(p["name"], {"name": p["name"], "games": 0, "goals": 0, "assists": 0, "key_passes": 0,
                                           "tackles_won": 0, "tackles_att": 0, "passes_made": 0, "passes_att": 0, "shots": 0,
                                           "shots_on": 0, "ratings": [], "mom": 0, "pos": p["pos"], "tags": {}, "rage_quits": 0,
                                           "record": {"W": 0, "D": 0, "L": 0}, "signals": [], "log": []})
            s = p["stats"]
            a["games"] += 1
            a["record"][m["result"]] += 1
            for k_out, k_in in (("goals", "goals"), ("assists", "assists"), ("tackles_won", "tackles_made"), ("tackles_att", "tackles_att"),
                                ("passes_made", "passes_made"), ("passes_att", "passes_att"), ("shots", "shots"), ("mom", "mom")):
                a[k_out] += s.get(k_in) or 0
            a["key_passes"] += s.get("key_passes") or 0
            a["shots_on"] += s.get("shots_on") or 0
            a["ratings"].append(s["rating"])
            a["rage_quits"] += s.get("rage_quit", 0)
            a["log"].append({"match": i, "opp": m["opponent"]["name"], "score": f"{m['gf']}-{m['ga']}", "result": m["result"],
                             "rating": s["rating"], **({"rage_quit": True} if s.get("rage_quit") else {})})
            for x in p.get("signals", []):
                a["signals"].append({**x, "match": i, "opp": m["opponent"]["name"]})
            for w in p["weaknesses"]:
                a["tags"][w["tag"]] = a["tags"].get(w["tag"], 0) + 1
    out = []
    for a in agg.values():
        a["avg_rating"] = round(sum(a["ratings"]) / len(a["ratings"]), 2)
        a["best_rating"], a["worst_rating"] = max(a["ratings"]), min(a["ratings"])
        a["top_issue"] = max(a["tags"], key=a["tags"].get) if a["tags"] else None
        a["pass_pct"] = _pct_of(a["passes_made"], a["passes_att"])
        a["tackle_pct"] = _pct_of(a["tackles_won"], a["tackles_att"])
        u = usual.get(a["name"], [])
        if len(u) >= 3:
            a["usual"] = {"rating": round(sum(x["rating"] for x in u[-15:]) / len(u[-15:]), 2),
                          "pass_pct": _pct_of(sum(x["passes_made"] for x in u[-15:]), sum(x["passes_att"] for x in u[-15:])),
                          "tackle_pct": _pct_of(sum(x["tackles_made"] for x in u[-15:]), sum(x["tackles_att"] for x in u[-15:])),
                          "matches": len(u)}
        a["lowlights"], a["highlights"] = _pick_signals(a, ("ugly", "bad"), 3), _pick_signals(a, ("good",), 2)
        del a["ratings"], a["tags"], a["signals"]
        out.append(a)
    return sorted(out, key=lambda a: -a["avg_rating"])


TEAMWIDE = {"scoreline", "ladder", "opp_strength", "stats_missing"}


def _pick_signals(a, sides, limit):
    """Strongest distinct signals for the day (team-wide ones left for the team section)."""
    items = sorted((x for x in a["signals"] if x["side"] in sides and x["metric"] not in TEAMWIDE),
                   key=lambda x: (-(x["w"] + (4 if x["side"] == "ugly" else 0))))
    out, fams = [], set()
    # day-level verdicts first: they sum up the whole day, not one match
    u = a.get("usual")
    if u and "bad" in sides:
        if a["avg_rating"] <= u["rating"] - 0.7:
            out.append(f"Averaged {a['avg_rating']:.1f} on the day against a usual {u['rating']:.1f}")
            fams.add("rating")
        if a["pass_pct"] is not None and u["pass_pct"] and a["passes_att"] >= 15 and a["pass_pct"] <= u["pass_pct"] - 8:
            out.append(f"Passed at {a['pass_pct']}% across the day ({a['passes_made']} of {a['passes_att']}), down from a usual {u['pass_pct']}%")
            fams.add("passing")
    if a["rage_quits"] and "bad" in sides:
        out.insert(0, f"Rage quit {a['rage_quits']} time{'s' if a['rage_quits'] > 1 else ''} today")
        fams.add("rage_quit")
    for x in items:
        f = _family(x["metric"])
        if f in fams or len(out) >= limit:
            continue
        out.append(f"Match {x['match']} vs {x['opp']}: {x['text']}")
        fams.add(f)
    return out[:limit]


def build(day, matches, cfg, table=None, rotation=None, story=None):
    """Build the summary data (everything except the speech)."""
    start, end = window(day, cfg)
    dm = [m for m in matches if start.timestamp() <= m["ts"] < end.timestamp()]
    before = [m for m in matches if m["ts"] < start.timestamp()]
    baseline = team_baseline(before)
    rec = {"W": 0, "D": 0, "L": 0}
    for m in dm:
        rec[m["result"]] += 1
    score = score_day(dm, baseline, story)
    players = summarize_players(dm, before)
    best = max(dm, key=lambda m: (m["gf"] - m["ga"], m["gf"]))
    worst = min(dm, key=lambda m: (m["gf"] - m["ga"], m["gf"]))
    issues = {}
    for m in dm:
        for p in m["players"]:
            for w in p["weaknesses"]:
                issues[w["tag"]] = issues.get(w["tag"], 0) + 1
    team_issue = max(issues, key=issues.get) if issues else None
    run = longest = 0
    for m in dm:
        run = run + 1 if m["result"] == "L" else 0
        longest = max(longest, run)
    half = len(dm) // 2
    first, second = dm[:half], dm[half:]
    pts = lambda ms: sum({"W": 3, "D": 1, "L": 0}[m["result"]] for m in ms)
    opp_r = [q["stats"]["rating"] for m in dm for q in m.get("opp_players", []) if not q["stats"].get("rage_quit")]
    our_r = [q["stats"]["rating"] for m in dm for q in m["players"] if not q["stats"].get("rage_quit")]
    quits = [{"name": p["name"], "match": i, "opp": m["opponent"]["name"], "score": f"{m['gf']}-{m['ga']}"}
             for i, m in enumerate(dm, 1) for p in m["players"] if p["stats"].get("rage_quit")]
    return {
        "date": day.isoformat(),
        "label": f"{day:%a, %b} {day.day}",
        "title": f"{day:%b} {day.day} Daily Summary",
        "games": len(dm), "record": rec, "gf": sum(m["gf"] for m in dm), "ga": sum(m["ga"] for m in dm),
        "points": 3 * rec["W"] + rec["D"], "baseline": baseline,
        "score": score, "grade": grade_for(score),
        "players": players, "active": [p["name"] for p in players],
        "mvp": players[0]["name"] if players else None,
        "best_match": {"id": best["id"], "score": f"{best['gf']}-{best['ga']}", "opp": best["opponent"]["name"], "result": best["result"]},
        "worst_match": {"id": worst["id"], "score": f"{worst['gf']}-{worst['ga']}", "opp": worst["opponent"]["name"], "result": worst["result"]},
        "team_issue": team_issue,
        "team": {"longest_losing_run": longest, "conceded_per_match": round(sum(m["ga"] for m in dm) / len(dm), 2),
                 "first_half_points": pts(first), "second_half_points": pts(second), "rage_quits": quits,
                 "their_avg_rating": round(sum(opp_r) / len(opp_r), 2) if opp_r else None,
                 "our_avg_rating": round(sum(our_r) / len(our_r), 2) if our_r else None,
                 "four_goal_losses": sum(1 for m in dm if m["ga"] - m["gf"] >= 4)},
        "ladder_day": story,
        "matches": [{"id": m["id"], "ts": m["ts"], "result": m["result"], "gf": m["gf"], "ga": m["ga"], "opp": m["opponent"]["name"]} for m in dm],
        "table": table,
    }


def key_stats(s):
    """Short stat lines shown under the speech (notification and site)."""
    r = s["record"]
    lines = [f"Day: {r['W']}W {r['D']}D {r['L']}L from {_plural(s['games'], 'match', 'matches')} · {s['gf']} scored, {s['ga']} conceded"]
    b = s.get("baseline") or {}
    if b.get("weight"):
        day_ppg = (3 * r["W"] + r["D"]) / s["games"]
        lines.append(f"Vs our usual: {day_ppg:.1f} pts per game today, {b['ppg']:.1f} normally ({b['matches']} matches)")
    if s["mvp"]:
        p = s["players"][0]
        lines.append(f"Player of the day: {p['name']} ({p['avg_rating']:.1f} avg, {_plural(p['goals'], 'goal')}, {_plural(p['assists'], 'assist')})")
    ld = s.get("ladder_day")
    if ld and ld.get("start") and ld.get("end"):
        a, b = ld["start"], ld["end"]
        lines.append(f"Ladder: started {_ladder_short(a)}, finished {_ladder_short(b)}")
    q = (s.get("team") or {}).get("rage_quits") or []
    if q:
        who = {}
        for x in q:
            who[x["name"]] = who.get(x["name"], 0) + 1
        lines.append("Rage quits: " + ", ".join(f"{n}" + (f" x{c}" if c > 1 else "") for n, c in who.items()))
    t = s.get("table")
    if t:
        lines.append(f"League: {t['stage_label']}")
        lines += t["status"]
    return lines


def _ladder_short(t):
    if t["stage"] == "promotion":
        return f"{t['division_name']}, promotion matches"
    if t["stage"] == "relegation":
        return f"{t['division_name']}, relegation match next"
    return f"{t['division_name']}, {t['points']}/{t['target']} pts, {t['lives']} of {t['max_lives']} chances" if t.get("target") else f"{t['division_name']}, {t['points']} pts"


# ------------------------------------------------------- the speech: Claude

SYSTEM_PROMPT = """You write the nightly post-session speech for a Pro Clubs team in EA Sports FC 27, in the voice of a coach modeled on Ted Lasso: folksy Midwestern warmth, homespun metaphors, gentle humor and relentless belief in people. Use original lines; do not quote the TV show.

It is a spoken transcript: plain paragraphs, no headings, no bullet points, no markdown, no stage directions. Length: 380 to 520 words (2 to 3 minutes spoken).

Judge the day objectively, like an honest analyst, from the data you are given: results and scorelines, goals conceded, the league ladder at the start and end of the day, ratings against each player's own usual, rage quits, and the team's baseline. Do not soften a bad day or inflate a good one. The letter grade has already been decided from the numbers; your words must match it, and you may say the grade out loud. Never mention the internal 0-20 score.

The ladder: say plainly where we started the day and where we finished it (division and stage), and what happened in between (e.g. relegated, promotion series failed, relegation match next). Do not list every ladder step.

Players: talk to every player by name. Use their "lowlights" and "highlights" (each is a real fact with a number). On a poor day (grade D or F) every player gets 2-3 explicit things they did badly, with the numbers; still credit a genuine positive where one exists. A rating marked rage_quit means the player quit the match: call it out directly but without cruelty. Their averages already count a rage quit as 5.0.

Follow the tone guidance exactly. Whatever the tone, Coach always brings it home in classic Ted Lasso style and the very last lines are hopeful and uplifting. Do not invent statistics that are not in the data."""


def claude_facts(summary):
    facts = {k: summary.get(k) for k in ("label", "grade", "games", "record", "gf", "ga", "best_match", "worst_match", "matches", "team")}
    facts["club_name"] = summary.get("club")
    facts["players"] = [{k: p.get(k) for k in ("name", "pos", "games", "record", "avg_rating", "best_rating", "worst_rating", "goals", "assists",
                                              "key_passes", "shots", "shots_on", "pass_pct", "passes_made", "passes_att", "tackle_pct", "tackles_won",
                                              "tackles_att", "mom", "rage_quits", "usual", "lowlights", "highlights", "log", "all_time")}
                        for p in summary["players"]]
    b = summary.get("baseline") or {}
    facts["our_usual"] = ({"points_per_game": b["ppg"], "goal_diff_per_game": b["gd"], "avg_rating": b["rating"], "matches": b["matches"],
                           "note": "Judge the day against this team's own usual as well as league standards."}
                          if b.get("weight") else None)
    facts["main_team_issue"] = pb.TAG_TITLES.get(summary["team_issue"]) if summary.get("team_issue") else None
    facts["coaching_points_for_that_issue"] = pb.tips_for(summary["team_issue"], "_", 4) if summary.get("team_issue") else []
    ld = summary.get("ladder_day")
    if ld:
        facts["ladder_today"] = {"start_of_day": ld["start"] and ld["start"]["spoken"], "end_of_day": ld["end"]["spoken"],
                                 "relegated_from": ld.get("relegated_from"), "promoted_from": ld.get("promoted_from"),
                                 "facing_relegation_match_next": ld.get("facing_relegation"),
                                 "events": [e["text"] for e in ld.get("events", []) if e.get("kind") != "manual"]}
    if summary.get("table"):
        facts["ladder_now"] = {"where_we_are": summary["table"]["spoken"], "status": summary["table"]["status"]}
    facts["previous_summary"] = summary.get("previous")
    facts["season_so_far"] = summary.get("season_so_far")
    return facts


def claude_speech(summary, tone):
    """Write the speech with Claude. Returns None if no key or on any failure."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None
    facts = claude_facts(summary)
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
                       f"Grade for today: {summary['grade']}\nTone guidance for today: {tone}\n\nToday's data (JSON):\n"
                       f"{json.dumps(facts, indent=1, ensure_ascii=False)}\n\nWrite the speech."}],
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
TABLE = ["Where does that leave us? {spoken}. Nobody said climbing was easy, but the view's worth it.",
         "A word on the ladder, because the ladder never lies: {spoken}. I like our chances. I always like our chances.",
         "League check: {spoken}. That's not pressure, that's an invitation."]
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
    return "scathing" if score <= 2 else "low" if score <= 8 else "mid" if score <= 13 else "high"


SCATHING_OPEN = [
    "Sit down. All of you. No, don't look at your phones, look at me. That was the worst football I've watched since I started this job, and I once watched a goat referee a pee-wee match.",
    "I've been chewing on what to say for an hour and I keep landing on the same word: unacceptable. Not you as people. What we put on that pitch tonight.",
    "Y'all, I am not gonna sugarcoat this, because sugar is for biscuits and tonight doesn't deserve a biscuit. That was a mess from the first whistle to the last.",
    "Grab a seat and grab a mirror, because the problem tonight isn't the other team. It's us.",
]
SCATHING_LADDER = [
    "We started the day {start}. We finished it {end}. {fall} Let that sink all the way in, because I need it to.",
    "This morning we were {start}. Tonight we're {end}. {fall} That's not bad luck. That's a day of bad decisions stacked on top of each other.",
    "Here's the whole story in two sentences. We woke up {start}. We're going to bed {end}. {fall}",
]
SCATHING_PLAYER = [
    "{name}, you're not hiding from this one: {items}.",
    "{name}. {items}. That's not the player I know.",
    "{name}, I wrote yours down so I'd get it right: {items}.",
    "And {name}: {items}. We both know you're better than that.",
    "{name}, let's be honest with each other: {items}.",
]
SCATHING_TURN = [
    "Now. I've said my piece, and every word of it was true. But here's something else that's true: I wouldn't be this upset if I didn't believe in every single one of you. You don't yell at a tomato plant for not growing unless you know it can.",
    "Okay. Deep breath. That's the hard part done. Because here's what a day like this really is: it's the bottom of the hill. And the nice thing about the bottom of the hill is there's only one direction left to go.",
    "That's the last time I'm raising my voice about today. Now listen, because this next part matters more. Bad days don't make bad teams. How you answer them does.",
]
SCATHING_CLOSE = [
    "So tomorrow we walk in, we win that relegation match, and we start the climb back. Together. I believe in this team more right now than I did this morning, because now I know exactly what we're fixing. Get some sleep. Believe.",
    "Go home. Rest. Drink some water. Tomorrow's a brand-new pitch, and I want us to stomp all over it. I'm proud to be your coach, today of all days. Believe.",
    "Here's my promise: I'm not going anywhere, and neither are you. We're gonna fix this one pass, one tackle, one match at a time, and one day we'll laugh about tonight. Believe.",
]


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


def _join(items):
    items = [x[0].lower() + x[1:] for x in items]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def scathing_speech(s, pick):
    """The F-day speech: lay into them, every player's lowlights, then turn it home."""
    r = s["record"]
    paras = [pick("d_scath_open", SCATHING_OPEN),
             (f"{s['games']} matches. {r['W']} won, {r['D']} drawn, {r['L']} lost. {s['gf']} scored and {s['ga']} conceded. "
             + (f"We lost {s['team']['four_goal_losses']} of them by four or more. " if s["team"].get("four_goal_losses") else "")
             + (f"At one point we lost {s['team']['longest_losing_run']} on the bounce." if s["team"].get("longest_losing_run", 0) >= 3 else "")).strip()]
    ld = s.get("ladder_day")
    if ld and ld.get("start"):
        fall = (f"We got relegated out of {ld['relegated_from']}, and now we've got a relegation match to keep us in {ld['end']['division_name']}."
                if ld.get("relegated_from") and ld.get("facing_relegation") else
                f"We got relegated out of {ld['relegated_from']}." if ld.get("relegated_from") else
                "And we've burned every chance we had." if ld.get("facing_relegation") else "")
        paras.append(pick("d_scath_ladder", SCATHING_LADDER).format(start=_ladder_short(ld["start"]).replace(",", " with", 1),
                                                                   end=_ladder_short(ld["end"]).replace(",", " with", 1), fall=fall))
    quits = s["team"].get("rage_quits") or []
    if quits:
        names = sorted({q["name"] for q in quits})
        paras.append(f"And some of us didn't even finish. {' and '.join(names)}, you walked off. "
                     "I understand frustration. I don't accept leaving your teammates short.")
    lines = []
    for p in s["players"]:
        items = p.get("lowlights") or []
        if items:
            lines.append(pick("d_scath_player", SCATHING_PLAYER).format(name=p["name"], items=_join(items[:3])))
        if p.get("highlights"):
            lines.append(f"The one thing I'll keep from your day, {p['name']}: {p['highlights'][0][0].lower() + p['highlights'][0][1:]}.")
    paras.append(" ".join(lines))
    if s.get("team_issue"):
        tips = pb.tips_for(s["team_issue"], "_", 12)
        paras.append(pick("d_focus", FOCUS).format(issue=pb.TAG_TITLES[s["team_issue"]].lower(), tip=pick("t_" + s["team_issue"], tips)))
    paras.append(pick("d_scath_turn", SCATHING_TURN))
    paras.append(pick("d_story_low", STORY["low"]))
    paras.append(pick("d_rally_low", RALLY["low"]))
    paras.append(pick("d_scath_close", SCATHING_CLOSE))
    return paras


def builtin_speech(s, rotation):
    """Returns (speech, phrase ids used) so later days rotate away from them."""
    pick = Picker(f"daily|{s['date']}", rotation)
    mood = _mood(s["score"])
    if mood == "scathing":
        return _an("\n\n".join(scathing_speech(s, pick))), sorted(pick.used)
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
    if t and t["status"]:
        paras.append(pick("d_table", TABLE).format(spoken=t["spoken"]))
    paras.append(pick("d_rally_" + mood, RALLY[mood]))
    # keep it a 2-3 minute speech (~320+ words): add more beats if it ran short
    extra = [("d_core_", CORE), ("d_rally_", RALLY), ("d_story_", STORY), ("d_core_", CORE)]
    while len(" ".join(paras).split()) < 320 and extra:
        key, pool = extra.pop(0)
        paras.insert(-1, pick(key + mood, pool[mood]))
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
    from . import league
    cfg = settings(config)
    start, end = window(day, cfg)
    story = league.day_story(matches, config, start.timestamp(), end.timestamp())
    s = build(day, matches, cfg, table, story=story)
    s["club"] = config["club"]["name"]
    prev = [x for x in load_all() if x["date"] < s["date"]]
    if prev:
        s["previous"] = {"date": prev[-1]["date"], "grade": prev[-1]["grade"], "record": prev[-1]["record"]}
    season = [m for m in matches if m["ts"] < end.timestamp() and m.get("season") == (next((m["season"] for m in matches if start.timestamp() <= m["ts"] < end.timestamp()), None))]
    if season:
        r = {"W": 0, "D": 0, "L": 0}
        for m in season:
            r[m["result"]] += 1
        s["season_so_far"] = {"season": season[0]["season"], "record": r, "gf": sum(m["gf"] for m in season), "ga": sum(m["ga"] for m in season)}
    for p in s["players"]:
        rows = [q["stats"] for m in matches if m["ts"] < end.timestamp() for q in m["players"] if q["name"] == p["name"]]
        rq = sum(1 for x in rows if x.get("rage_quit"))
        p["all_time"] = {"matches": len(rows), "avg_rating": round(sum(x["rating"] for x in rows) / len(rows), 2), "rage_quits": rq}
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
        if closed and len(ms) >= cfg["min_games"] and not path_for(day).exists() and day.isoformat() not in cfg["hold"]:
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


# Extra phrasing for the speech (about 5x the pools above), merged append-only
import sys as _sys  # noqa: E402
from . import daily_more as _daily_more  # noqa: E402
_daily_more.merge(_sys.modules[__name__])
