"""Everything Coach Lasso weighs before writing a player's note.

Every stat in a performance is checked against eight frames of reference:

  usual      the player's last 10 matches (how far off their normal, in spread)
  all-time   their best and worst ever for us
  team       where they ranked among our humans in the same match
  share      their share of the team's total
  opponent   the other side's humans in the same match
  session    earlier matches in the same session (a run of matches < 3h apart)
  streak     how many matches running it has been good or bad
  benchmark  the position's league benchmark

plus the match itself: scoreline, ladder stakes, opponent strength, how deep
into the session it was, rage quits, red cards and time idle. Each check that
says something becomes a signal with a side (good / bad / ugly) and a weight;
the note keeps only the strongest few, so the bullet count stays the same
while the bullets get sharper.
"""
from statistics import mean, pstdev

from . import playbook as pb

# key: (label, higher is better, kind)
METRICS = {
    "rating": ("match rating", True, "rating"),
    "goals": ("goals", True, "count"),
    "assists": ("assists", True, "count"),
    "shots": ("shots", True, "count"),
    "shots_on": ("shots on target", True, "count"),
    "shot_accuracy": ("shot accuracy", True, "pct"),
    "conversion": ("shot conversion", True, "pct"),
    "key_passes": ("key passes", True, "count"),
    "passes_att": ("passes attempted", True, "count"),
    "passes_made": ("completed passes", True, "count"),
    "passes_missed": ("misplaced passes", False, "count"),
    "pass_pct": ("pass accuracy", True, "pct"),
    "tackles_att": ("tackles attempted", True, "count"),
    "tackles_made": ("tackles won", True, "count"),
    "missed_tackles": ("missed tackles", False, "count"),
    "tackle_pct": ("tackle success", True, "pct"),
    "saves": ("saves", True, "count"),
    "conceded": ("goals conceded", False, "count"),
    "save_pct": ("save percentage", True, "pct"),
    "idle_share": ("time idle", False, "share"),
    "goal_involvements": ("goal involvements", True, "count"),
    "actions": ("on-ball actions", True, "count"),
    "errors": ("giveaways", False, "count"),  # misplaced passes + missed tackles
}
LOOP_SKIP = {"idle_share"}  # handled on its own, tiny values aren't news
GK_METRICS = {"saves", "conceded", "save_pct"}
GK_SKIP = {"goals", "shots", "shots_on", "shot_accuracy", "conversion", "tackles_att", "tackles_made", "missed_tackles", "tackle_pct"}
GATES = {"pass_pct": ("passes_att", 5), "tackle_pct": ("tackles_att", 3), "shot_accuracy": ("shots", 2),
         "conversion": ("shots", 2), "save_pct": ("shots_faced", 3)}
SPREAD_FLOOR = {"count": 1.0, "pct": 8.0, "rating": 0.5, "share": 0.08}
SESSION_GAP = 3 * 3600


def fmt(key, v):
    kind = METRICS[key][2]
    if v is None:
        return "-"
    if kind == "pct":
        return f"{v:.0f}%"
    if kind == "share":
        return f"{v * 100:.0f}%"
    if kind == "rating":
        return f"{v:.1f}"
    return f"{v:.0f}"


def _ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _ok(key, s):
    """Is this stat meaningful for this performance (enough attempts)?"""
    if s.get(key) is None:
        return False
    gate = GATES.get(key)
    return not gate or (s.get(gate[0]) or 0) >= gate[1]


def _applies(key, pos):
    return (key in GK_METRICS) == (pos == "goalkeeper") or (pos == "goalkeeper" and key not in GK_SKIP and key not in GK_METRICS)


def sessions(matches):
    """match id -> list of earlier matches in the same session (oldest first)."""
    out, run = {}, []
    for m in sorted(matches, key=lambda x: x["ts"]):
        if run and m["ts"] - run[-1]["ts"] > SESSION_GAP:
            run = []
        out[m["id"]] = list(run)
        run.append(m)
    return out


class Collector:
    def __init__(self):
        self.items, self.checked = [], 0

    def check(self):
        self.checked += 1

    def add(self, side, w, metric, frame, text, tip_tag=None):
        self.items.append({"side": side, "w": round(w, 2), "metric": metric, "frame": frame, "text": text, "tip": tip_tag})


TIP_FOR = {"pass_pct": "passing_accuracy", "passes_missed": "forcing_passes", "passes_att": "involvement", "key_passes": "progression",
           "tackle_pct": "tackle_timing", "missed_tackles": "tackle_timing", "tackles_att": "defensive_work_rate", "tackles_made": "defensive_work_rate",
           "shots": "shot_volume", "shot_accuracy": "shot_selection", "shots_on": "shot_selection", "conversion": "finishing",
           "save_pct": "shot_stopping", "conceded": "shot_stopping", "idle_share": "idle"}


def player_signals(m, p, history, earlier_in_session, ladder_event=None, club_pos=None):
    """All signals for one player's one match. `history` = their earlier rows."""
    s, pos, c = p["stats"], p["pos"], Collector()
    club_pos = club_pos or {}
    mates = [q for q in m["players"] if q["name"] != p["name"]]
    ours = m["players"]
    theirs = [q for q in m.get("opp_players", []) if not q["stats"].get("rage_quit")]
    every = [h["stats"] for h in history]
    prev = [x for x in every if not x.get("rage_quit") and not x.get("stats_missing")]  # real performances only
    recent = prev[-10:]
    played = s["minutes"] > 0 and not s.get("rage_quit")

    # ---------------------------------------------------------- the match itself
    margin = m["gf"] - m["ga"]
    c.check()
    if s.get("rage_quit"):
        n = sum(1 for h in every if h.get("rage_quit")) + 1
        c.add("ugly", 10, "rage_quit", "match",
              f"Rage quit. EA logged a {s['raw_rating']:.1f} and {s['minutes']} minutes, leaving the team a player short"
              + (f". That's your {_ordinal(n)} walk-off for us" if n > 1 else ""))
    c.check()
    quitters = [q["name"] for q in mates if q["stats"].get("rage_quit")]
    if quitters and played:
        c.add("good", 4.5, "stayed", "match", f"Stayed on and finished the match after {' and '.join(quitters)} walked off")
    c.check()
    if s["red_cards"]:
        c.add("ugly", 8, "red_cards", "match", "Red card: the team played a player down for the rest of it", "discipline")
    c.check()
    if margin <= -4:
        defensive = pos in ("goalkeeper", "defender")
        c.add("ugly" if defensive else "bad", 6.5 if defensive else 4, "scoreline", "match",
              f"We shipped {m['ga']} goals to {m['opponent']['name']} and lost by {-margin}")
    elif margin == -1:
        c.add("bad", 2.5, "scoreline", "match", f"A one-goal loss ({m['gf']}-{m['ga']}): a single moment decided it")
    elif margin >= 3:
        c.add("good", 3.5, "scoreline", "match", f"Part of a {m['gf']}-{m['ga']} beating of {m['opponent']['name']}")
    c.check()
    if s.get("mom") and m["result"] == "L":
        c.add("good", 6, "mom", "match", "Man of the Match in a losing side: the bright spot on a dark night")
    c.check()
    if ladder_event:
        k, text = ladder_event.get("kind"), ladder_event.get("text", "")
        if k == "relegated":
            c.add("ugly", 7, "ladder", "ladder", f"This was the relegation match we lost: {text}")
        elif k == "relegation_match_due":
            c.add("bad", 5.5, "ladder", "ladder", f"This loss burned our last chance in {_div(ladder_event)} and set up a relegation match")
        elif k == "promotion_failed":
            c.add("bad", 5, "ladder", "ladder", f"This result ended our promotion push in {_div(ladder_event)}")
        elif k == "promoted":
            c.add("good", 8, "ladder", "ladder", f"This was the win that got us promoted out of {_div(ladder_event)}")
        elif k == "qualified":
            c.add("good", 6, "ladder", "ladder", f"This result took us into promotion matches in {_div(ladder_event)}")
        elif k == "survived":
            c.add("good", 6, "ladder", "ladder", f"Relegation match survived: we stayed in {_div(ladder_event)}")
        elif k == "promo_match":
            c.add("good" if m["result"] == "W" else "bad", 4, "ladder", "ladder",
                  f"A promotion match, and we {'won it' if m['result'] == 'W' else 'drew it' if m['result'] == 'D' else 'lost it'}")
        elif m["result"] == "L" and ladder_event.get("stage") == "points":
            c.add("bad", 2.5, "ladder", "ladder", f"That loss cost us one of our chances in {_div(ladder_event)}")
    c.check()
    our_r = [q["stats"]["rating"] for q in ours if not q["stats"].get("rage_quit")]
    their_r = [q["stats"]["rating"] for q in theirs]
    if our_r and their_r and abs(mean(their_r) - mean(our_r)) >= 1.2:
        better = mean(our_r) > mean(their_r)
        c.add("good" if better else "bad", 3, "opp_strength", "opponent",
              f"Their humans averaged {mean(their_r):.1f} to our {mean(our_r):.1f}" + ("; we out-played them man for man" if better else "; we were second best man for man"))

    # session fatigue / trend
    sess = [q for x in earlier_in_session for q in x["players"] if q["name"] == p["name"]
            and not q["stats"].get("rage_quit") and not q["stats"].get("stats_missing")]
    c.check()
    if played and len(sess) >= 2:
        first = mean(q["stats"]["rating"] for q in sess[:3])
        idx = len(earlier_in_session) + 1
        if s["rating"] <= first - 1.0 and idx >= 5:
            c.add("bad", 5, "rating", "session", f"Match {idx} of the session and your rating had slid from {first:.1f} early on to {s['rating']:.1f}")
        elif s["rating"] >= first + 1.0:
            c.add("good", 4.5, "rating", "session", f"Match {idx} of the session and you got stronger: {first:.1f} early on, {s['rating']:.1f} here")
        c.check()
        rs = [q["stats"]["rating"] for q in sess]
        if s["rating"] < min(rs) and len(rs) >= 3:
            c.add("bad", 3.5, "rating", "session", f"Lowest rating of your {len(rs) + 1} matches this session")
        elif s["rating"] > max(rs) and len(rs) >= 3:
            c.add("good", 3.5, "rating", "session", f"Your best rating of the session's {len(rs) + 1} matches")

    # player's result run
    c.check()
    run = 0
    for h in reversed(every):
        if h["result"] == "L":
            run += 1
        else:
            break
    if m["result"] == "L" and run >= 2:
        c.add("bad", 2 + min(run, 5) * 0.5, "results", "streak", f"Your {_ordinal(run + 1)} straight loss")
    elif m["result"] == "W" and run >= 3:
        c.add("good", 4, "results", "streak", f"Snapped a {run}-match losing run")

    c.check()
    if s.get("stats_missing") and not s.get("rage_quit"):
        c.add("bad", 2, "stats_missing", "match", f"EA logged a {s['rating']:.1f} but recorded no passes, tackles or shots for you, so this one's judged on the rating alone")
    if not played or s.get("stats_missing"):
        return c

    # ------------------------------------------------------------ every stat
    for key, (label, up, kind) in METRICS.items():
        if key in LOOP_SKIP or not _applies(key, pos) or not _ok(key, s):
            continue
        cur = s[key]
        better = (lambda a, b: a > b) if up else (lambda a, b: a < b)

        # usual
        c.check()
        vals = [h[key] for h in recent if _ok(key, h)]
        if len(vals) >= 3:
            avg = mean(vals)
            spread = max(pstdev(vals), SPREAD_FLOOR[kind])
            z = (cur - avg) / spread * (1 if up else -1)
            if abs(z) >= 1.0 and not (kind == "count" and cur == 0 and avg < 1):
                side = "good" if z > 0 else "bad"
                ugly = side == "bad" and ((key == "rating" and avg - cur >= 1.5) or (key == "pass_pct" and cur < 55 and s["passes_att"] >= 10))
                c.add("ugly" if ugly else side, min(9, 3 + abs(z) * 1.5), key, "usual",
                      f"{label.capitalize()} {fmt(key, cur)}, {'up' if cur > avg else 'down'} from your usual {fmt(key, avg)}", TIP_FOR.get(key))

        # all-time
        c.check()
        allv = [h[key] for h in prev if _ok(key, h)]
        if len(allv) >= 5 and key != "rating":
            if better(cur, max(allv) if up else min(allv)) and (cur > 0 or not up):
                c.add("good", 6, key, "alltime", f"{'Most' if up else 'Fewest'} {label} you've had in {len(allv) + 1} matches for us ({fmt(key, cur)})")
            elif better(min(allv) if up else max(allv), cur):
                c.add("bad", 5, key, "alltime", f"{'Fewest' if up else 'Most'} {label} in your {len(allv) + 1} matches for us ({fmt(key, cur)})", TIP_FOR.get(key))

        # team
        c.check()
        team = [(q["name"], q["stats"][key]) for q in ours if _ok(key, q["stats"]) and not q["stats"].get("rage_quit") and not q["stats"].get("stats_missing")
                and _applies(key, q["pos"])]
        if len(team) >= 3:
            ranked = sorted(team, key=lambda t: t[1], reverse=up)
            if ranked[0][0] == p["name"] and better(ranked[0][1], ranked[1][1]):
                c.add("good", 4 if key != "rating" else 5, key, "team",
                      ("Top-rated Grizzly in the match" if key == "rating" else f"Team-high {fmt(key, cur)} {label}") if up
                      else f"Fewest {label} on the team ({fmt(key, cur)})")
            elif ranked[-1][0] == p["name"] and better(ranked[-2][1], ranked[-1][1]):
                top = ranked[0]
                c.add("bad", 3.5 if key != "rating" else 4.5, key, "team",
                      f"{'Lowest' if up else 'Most'} {label} on the team: {fmt(key, cur)} (best was {top[0]}'s {fmt(key, top[1])})", TIP_FOR.get(key))

        # share of the team total
        c.check()
        if kind == "count" and up:
            total = sum(q["stats"].get(key) or 0 for q in ours)
            if total >= 4:
                share = cur / total
                if share >= 0.5 and len(ours) >= 3:
                    c.add("good", 4, key, "share", f"{fmt(key, cur)} of the team's {total} {label}: the team ran through you")
                elif cur == 0 and key in ("shots", "passes_att", "tackles_att") and len(ours) >= 3:
                    c.add("bad", 3.5, key, "share", f"None of the team's {total} {label}", TIP_FOR.get(key))

        # opponent's humans
        c.check()
        opp = [q["stats"][key] for q in theirs if _ok(key, q["stats"]) and _applies(key, q["pos"])]
        if opp and key in ("rating", "tackles_made", "passes_made", "pass_pct", "key_passes", "shots_on", "saves"):
            best = max(opp) if up else min(opp)
            if better(cur, best) and (cur > 0):
                c.add("good", 4.5, key, "opponent", f"Better {label} than any of their humans ({fmt(key, cur)} vs their best {fmt(key, best)})")
            if key == "rating":
                same = [q["stats"]["rating"] for q in theirs if q["pos"] == pos]
                c.check()
                if same and max(same) - cur >= 2.0:
                    c.add("ugly" if max(same) - cur >= 3.0 else "bad", 5 + (max(same) - cur), "rating", "opponent",
                          f"Their best {pb.LABELS.get(pos, pos).lower()} posted {max(same):.1f} to your {cur:.1f}")
                elif same and cur - max(same) >= 1.0:
                    c.add("good", 5, "rating", "opponent", f"Won your matchup: {cur:.1f} against their best {pb.LABELS.get(pos, pos).lower()}'s {max(same):.1f}")

        # session
        c.check()
        sv = [q["stats"][key] for q in sess if _ok(key, q["stats"])]
        if len(sv) >= 2 and key != "rating":
            if better(cur, max(sv) if up else min(sv)) and cur:
                c.add("good", 3, key, "session", f"Best {label} of your {len(sv) + 1} matches this session ({fmt(key, cur)})")
            elif better(min(sv) if up else max(sv), cur):
                c.add("bad", 3, key, "session", f"Worst {label} of your {len(sv) + 1} matches this session ({fmt(key, cur)})", TIP_FOR.get(key))

        # benchmark
        c.check()
        bench = pb.BENCHMARKS.get(pos, {}).get(key)
        if bench:
            top, poor, _ = bench
            if poor is not None and ((cur <= poor) if up else (cur >= poor)) and key in ("pass_pct", "tackle_pct", "save_pct") and (
                    (key == "pass_pct" and cur < 55) or (key == "tackle_pct" and cur == 0 and s["tackles_att"] >= 4) or (key == "save_pct" and cur < 40)):
                c.add("ugly", 7, key, "benchmark", f"{label.capitalize()} {fmt(key, cur)}"
                      + (f" ({s['passes_made']} of {s['passes_att']})" if key == "pass_pct" else
                         f" (0 of {s['tackles_att']})" if key == "tackle_pct" else f" ({s['saves']} saves, {s['conceded']} conceded)"), TIP_FOR.get(key))

        # last match
        c.check()
        if prev and _ok(key, prev[-1]):
            last = prev[-1][key]
            jump = (cur - last) / SPREAD_FLOOR[kind] * (1 if up else -1)
            if abs(jump) >= 3:
                c.add("good" if jump > 0 else "bad", 2.5, key, "last", f"{label.capitalize()} {fmt(key, cur)}, from {fmt(key, last)} in your previous match", TIP_FOR.get(key) if jump < 0 else None)

        # this season
        c.check()
        sea = [h["stats"][key] for h in history if _ok(key, h["stats"]) and h.get("season") == m.get("season")
               and not h["stats"].get("rage_quit") and not h["stats"].get("stats_missing")]
        if len(sea) >= 5:
            sa = mean(sea)
            gap = (cur - sa) / max(pstdev(sea), SPREAD_FLOOR[kind]) * (1 if up else -1)
            if abs(gap) >= 1.5:
                c.add("good" if gap > 0 else "bad", 2.5 + abs(gap) * 0.5, key, "season",
                      f"{label.capitalize()} {fmt(key, cur)} against a season average of {fmt(key, sa)}", TIP_FOR.get(key) if gap < 0 else None)

        # how you play when we win
        c.check()
        wins = [h[key] for h in prev if h["result"] == "W" and _ok(key, h)]
        if len(wins) >= 3 and m["result"] != "W":
            wa = mean(wins)
            gap = (cur - wa) / max(pstdev(wins), SPREAD_FLOOR[kind]) * (1 if up else -1)
            if gap <= -1.2:
                c.add("bad", 3 + abs(gap) * 0.6, key, "wins", f"In our wins you average {fmt(key, wa)} {label}; here it was {fmt(key, cur)}", TIP_FOR.get(key))

        # opponent average
        c.check()
        if opp:
            oa = mean(opp)
            gap = (cur - oa) / SPREAD_FLOOR[kind] * (1 if up else -1)
            if gap <= -3 and key in ("pass_pct", "tackles_made", "passes_made", "rating"):
                c.add("bad", 3, key, "opponent", f"Their humans averaged {fmt(key, oa)} {label}; you had {fmt(key, cur)}", TIP_FOR.get(key))

        # club history at this position
        c.check()
        club = club_pos.get((pos, key))
        if club and len(club) >= 8:
            ca = mean(club)
            gap = (cur - ca) / max(pstdev(club), SPREAD_FLOOR[kind]) * (1 if up else -1)
            if abs(gap) >= 1.6:
                c.add("good" if gap > 0 else "bad", 2.5 + abs(gap) * 0.4, key, "club",
                      f"{label.capitalize()} {fmt(key, cur)}; Grizzly {pb.LABELS.get(pos, pos).lower()}s usually manage {fmt(key, ca)}", TIP_FOR.get(key) if gap < 0 else None)

    # streaks on the headline numbers
    for key, good_at, bad_at in (("rating", 7.5, 6.5), ("pass_pct", 80, 70), ("tackle_pct", 50, 25)):
        c.check()
        if not _ok(key, s) or not _applies(key, pos):
            continue
        seq = [h[key] for h in prev if _ok(key, h)] + [s[key]]
        for side, test in (("good", lambda v: v >= good_at), ("bad", lambda v: v < bad_at)):
            n = 0
            for v in reversed(seq):
                if test(v):
                    n += 1
                else:
                    break
            if n >= 3:
                c.add(side, 3 + min(n, 6) * 0.4, key, "streak",
                      f"{_ordinal(n)} straight match {'at' if side == 'good' else 'under'} {fmt(key, good_at if side == 'good' else bad_at)} {METRICS[key][0]}",
                      TIP_FOR.get(key) if side == "bad" else None)

    # idle
    c.check()
    if s.get("idle_share", 0) >= 0.3:
        c.add("ugly", 7, "idle_share", "match", f"Idle for {s['idle_share'] * 100:.0f}% of the match", "idle")
    return c


def _div(ev):
    d = ev.get("division")
    return "Elite" if d == "Elite" else f"Division {d}" if d else "the division"


def annotate(matches, ladder_events=None):
    """Attach p['signals'] (and the count of checks) to every player in every match."""
    by_match = {e["match"]: e for e in (ladder_events or []) if e.get("match")}
    sess = sessions(matches)
    history, club_pos = {}, {}  # club_pos: (position, stat) -> every earlier value by any of our players there
    for m in sorted(matches, key=lambda x: x["ts"]):
        for p in m["players"]:
            c = player_signals(m, p, history.get(p["name"], []), sess.get(m["id"], []), by_match.get(m["id"]), club_pos)
            p["signals"] = sorted(c.items, key=lambda x: -x["w"])
            p["signals_checked"] = c.checked
        for p in m["players"]:
            history.setdefault(p["name"], []).append({"stats": p["stats"], "season": m.get("season")})
            if not p["stats"].get("rage_quit") and p["stats"]["minutes"] > 0:
                for key in METRICS:
                    if _ok(key, p["stats"]):
                        club_pos.setdefault((p["pos"], key), []).append(p["stats"][key])
