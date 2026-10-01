"""Turns raw EA matches into per-player, per-match analysis and long-run themes.

Only players in our club's `players` block are analysed. EA's Pro Clubs feed
lists human-controlled pros only - AI teammates never appear there.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone

from . import playbook as pb

# ---------------------------------------------------------------- normalising


def _i(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _pct(num, den):
    return round(100.0 * num / den, 1) if den else None


def season_for(ts, ea_season, seasons):
    day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    for s in seasons:
        if s["start"] <= day <= s["end"]:
            return s["name"]
    if ea_season and str(ea_season) != "0":
        return f"EA Season {ea_season}"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%B %Y")


# Hidden counters in match_event_aggregate_0, decoded against 4,764 live
# player-matches (see reference/ea-stats-reference.html, section 2).
EVENT_CODES = {"217": "shots_on", "218": "shots_off", "114": "key_passes"}


def decode_events(raw):
    counts = {}
    for item in (raw.get("match_event_aggregate_0") or "").split(","):
        code, _, n = item.partition(":")
        if code in EVENT_CODES and n.isdigit():
            counts[EVENT_CODES[code]] = int(n)
    if not counts and not raw.get("match_event_aggregate_0"):
        return None  # no counters recorded for this player
    return {k: counts.get(k, 0) for k in EVENT_CODES.values()}


def player_line(raw, result):
    goals, shots = _i(raw.get("goals")), _i(raw.get("shots"))
    ev = decode_events(raw)
    if ev:
        shots_on = min(max(ev["shots_on"], goals), shots) if shots else 0
        key_passes = ev["key_passes"]
    else:
        shots_on, key_passes = None, None
    real, idle = _i(raw.get("realtimegame")), _i(raw.get("realtimeidle"))
    p_att, p_made = _i(raw.get("passattempts")), _i(raw.get("passesmade"))
    t_att, t_made = _i(raw.get("tackleattempts")), _i(raw.get("tacklesmade"))
    saves, conceded = _i(raw.get("saves")), _i(raw.get("goalsconceded"))
    return {
        "rating": round(_f(raw.get("rating")), 2),
        "minutes": round(_i(raw.get("secondsPlayed")) / 60),
        "goals": goals,
        "assists": _i(raw.get("assists")),
        "shots": shots,
        "shots_missed": max(shots - goals, 0),
        "shots_on": shots_on,
        "shots_off": shots - shots_on if shots_on is not None else None,
        "shot_accuracy": _pct(shots_on, shots) if shots_on is not None else None,
        "finishing": _pct(goals, shots_on) if shots_on else None,
        "conversion": _pct(goals, shots),
        "key_passes": key_passes,
        "passes_att": p_att,
        "passes_made": p_made,
        "passes_missed": max(p_att - p_made, 0),
        "pass_pct": _pct(p_made, p_att),
        "tackles_att": t_att,
        "tackles_made": t_made,
        "missed_tackles": max(t_att - t_made, 0),
        "tackle_pct": _pct(t_made, t_att),
        "saves": saves,
        "conceded": conceded,
        "shots_faced": saves + conceded,
        "save_pct": _pct(saves, saves + conceded),
        "red_cards": _i(raw.get("redcards")),
        "clean_sheet": 1 if conceded == 0 and _i(raw.get("cleansheetsany")) else 0,
        "mom": _i(raw.get("mom")),
        "idle_share": round(idle / real, 2) if real else 0,
        "result": result,
    }


def normalise(raw, club_id, seasons, roster):
    cid = str(club_id)
    if cid not in raw.get("clubs", {}):
        return None
    ours = raw["clubs"][cid]
    opp_id = next((k for k in raw["clubs"] if k != cid), None)
    opp = raw["clubs"].get(opp_id, {})
    gf, ga = _i(ours.get("goals")), _i(ours.get("goalsAgainst"))
    result = "W" if _i(ours.get("wins")) else "L" if _i(ours.get("losses")) else "D"
    ts = _i(raw.get("timestamp"))
    players = []
    for pid, p in raw.get("players", {}).get(cid, {}).items():
        name = p.get("playername", pid)
        if roster and name not in roster:
            continue
        pos = p.get("pos", "midfielder").lower()
        players.append({
            "pid": pid,
            "name": name,
            "pos": pos if pos in pb.POSITIONS else "midfielder",
            "stats": player_line(p, result),
            "event_codes": p.get("match_event_aggregate_0", ""),
        })
    return {
        "id": str(raw["matchId"]),
        "ts": ts,
        "date": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
        "season": season_for(ts, ours.get("season_id"), seasons),
        "type": raw.get("_matchType", "leagueMatch"),
        "result": result,
        "gf": gf,
        "ga": ga,
        "dnf": _i(ours.get("winnerByDnf")) == 1,
        "opponent": {
            "name": opp.get("details", {}).get("name", "Opponent"),
            "id": opp_id,
            "crest": opp.get("details", {}).get("customKit", {}).get("crestAssetId"),
        },
        "players": players,
    }


# ---------------------------------------------------------- rating model

FEATURES = [
    ("goals", "Goals"),
    ("assists", "Assists"),
    ("key_passes", "Key passes"),
    ("shots_on", "Shots on target"),
    ("shots_off", "Shots off target"),
    ("passes_made", "Completed passes"),
    ("passes_missed", "Misplaced passes"),
    ("tackles_made", "Tackles won"),
    ("missed_tackles", "Missed tackles"),
    ("saves", "Saves"),
    ("conceded", "Goals conceded"),
    ("clean_sheet", "Clean sheet"),
    ("red_cards", "Red cards"),
    ("result_val", "Match result"),
]

# Rating points per action, from a per-position regression of EA's match
# rating on 4,764 live player-matches (top-40 clubs, 60+ minutes). Weights
# that were statistical noise are set to 0; red cards are rare in the sample
# so they use rounded values. Replaced by a model learned from your own
# matches once enough data exists.
BASELINE = {
    "forward": {
        "_intercept": 6.45, "goals": 0.61, "assists": 0.32, "key_passes": 0.14,
        "shots_on": 0.09, "missed_tackles": -0.013, "red_cards": -1.0, "result_val": 0.22,
    },
    "midfielder": {
        "_intercept": 6.98, "goals": 0.41, "assists": 0.20, "key_passes": 0.10,
        "shots_on": 0.03, "shots_off": -0.05, "passes_made": 0.013, "passes_missed": -0.034,
        "tackles_made": 0.20, "missed_tackles": -0.028, "conceded": -0.02,
        "red_cards": -1.0, "result_val": 0.20,
    },
    "defender": {
        "_intercept": 6.94, "goals": 0.33, "assists": 0.23, "key_passes": 0.14,
        "shots_on": 0.15, "passes_made": 0.009, "tackles_made": 0.25,
        "missed_tackles": -0.03, "conceded": -0.058, "red_cards": -2.0, "result_val": 0.05,
    },
    "goalkeeper": {
        "_intercept": 5.73, "saves": 0.16, "conceded": -0.41, "passes_made": 0.037,
        "clean_sheet": 0.14, "red_cards": -1.0, "result_val": 0.26,
    },
}


def _feature_vec(stats):
    s = dict(stats)
    s["result_val"] = {"W": 1, "D": 0, "L": -1}[stats["result"]]
    if s["shots_on"] is None:  # no event counters: treat goals as the on-target shots
        s["shots_on"], s["shots_off"] = s["goals"], s["shots"] - s["goals"]
    s["key_passes"] = s["key_passes"] or 0
    return [1.0] + [float(s[k]) for k, _ in FEATURES]


def baseline_weights(pos):
    w = BASELINE[pos]
    return [w["_intercept"]] + [w.get(k, 0.0) for k, _ in FEATURES]


def _solve(a, b):
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[piv] = m[piv], m[c]
        if abs(m[c][c]) < 1e-12:
            continue
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] if abs(m[i][i]) > 1e-12 else 0.0 for i in range(n)]


def fit_models(samples, min_samples, lam=8.0):
    """Ridge regression per position, shrunk towards the baseline weights."""
    models = {}
    by_pos = defaultdict(list)
    for pos, stats in samples:
        by_pos[pos].append(stats)
    for pos in pb.POSITIONS:
        w0 = baseline_weights(pos)
        rows = by_pos.get(pos, [])
        if len(rows) < min_samples:
            models[pos] = {"weights": w0, "learned": False, "n": len(rows)}
            continue
        k = len(w0)
        xtx = [[0.0] * k for _ in range(k)]
        xty = [0.0] * k
        for st in rows:
            x = _feature_vec(st)
            for i in range(k):
                xty[i] += x[i] * st["rating"]
                for j in range(k):
                    xtx[i][j] += x[i] * x[j]
        for i in range(k):
            xtx[i][i] += lam
            xty[i] += lam * w0[i]
        models[pos] = {"weights": _solve(xtx, xty), "learned": True, "n": len(rows)}
    return models


def rating_drivers(stats, model):
    w = model["weights"]
    x = _feature_vec(stats)
    base = w[0]
    drivers = []
    for (key, label), wi, xi in zip(FEATURES, w[1:], x[1:]):
        impact = wi * xi
        if abs(impact) >= 0.05:
            drivers.append({"key": key, "label": label, "count": int(xi), "impact": round(impact, 2)})
    predicted = base + sum(d["impact"] for d in drivers)
    other = stats["rating"] - predicted
    if abs(other) >= 0.1:
        drivers.append({
            "key": "other", "label": "Everything else",
            "count": None, "impact": round(other, 2),
        })
    drivers.sort(key=lambda d: d["impact"], reverse=True)
    return {"baseline": round(base, 2), "drivers": drivers, "learned": model["learned"]}


# ---------------------------------------------------- strengths/weaknesses


def _fmt(metric, value):
    if value is None:
        return "-"
    return f"{value:.0f}%" if metric in pb.PERCENT_METRICS else f"{value:.0f}"


# Position medians used by the interaction rules (from playbook benchmarks)
PASS_VOLUME_P50 = {"forward": 17, "midfielder": 20, "defender": 12, "goalkeeper": 99}
TACKLE_VOLUME_P75 = {"forward": 7, "midfielder": 6, "defender": 4, "goalkeeper": 99}


def assess(pos, s, minutes_factor, impact=None):
    """Grade one performance against position benchmarks, then apply the
    interaction rules that read stats in pairs (Stat Atlas, sections 6 and 9)."""
    strengths, weaknesses = [], []
    role = pb.LABELS[pos].lower()
    for metric, (good, poor, gate) in pb.BENCHMARKS[pos].items():
        value = s.get(metric)
        if value is None:
            continue
        if gate and (s.get(gate[0]) or 0) < gate[1]:
            continue
        # scale counting stats for partial matches
        scaled = value if metric in pb.PERCENT_METRICS else value / minutes_factor
        label = pb.METRIC_LABELS[metric]
        detail = f"{label}: {_fmt(metric, value)} (top quarter of {role}s: {_fmt(metric, good)}+)"
        if scaled >= good:
            strengths.append({"tag": pb.STRENGTH_FROM_METRIC[metric], "detail": detail})
        elif poor is not None and scaled <= poor:
            detail = f"{label}: {_fmt(metric, value)} (bottom quarter of {role}s is {_fmt(metric, poor)} or less)"
            weaknesses.append({"tag": pb.WEAKNESS_FROM_METRIC[metric], "detail": detail})

    # --- interaction rules
    pass_pct, passes = s.get("pass_pct"), s["passes_att"] / minutes_factor
    if pos != "goalkeeper" and pass_pct is not None and pass_pct < pb.PASS_BREAK_EVEN and passes >= PASS_VOLUME_P50[pos]:
        weaknesses = [w for w in weaknesses if w["tag"] != "passing_accuracy"]
        weaknesses.append({"tag": "forcing_passes", "detail":
                           f"{s['passes_made']}/{s['passes_att']} passes ({pass_pct:.0f}%) - below the ~72% point where extra passes start costing rating"})
    if pos == "midfielder" and passes >= 25 and s.get("key_passes") == 0:
        weaknesses.append({"tag": "progression", "detail": f"{s['passes_att']} passes but no key passes - plenty of the ball, little going forward"})
    tackle_pct = s.get("tackle_pct")
    if tackle_pct is not None and s["tackles_att"] / minutes_factor >= TACKLE_VOLUME_P75[pos] and tackle_pct < pb.DIVING_IN_SUCCESS:
        weaknesses.append({"tag": "tackle_timing", "detail":
                           f"Won {s['tackles_made']} of {s['tackles_att']} tackles ({tackle_pct:.0f}%) - diving in; each miss leaves a runner free"})
    if s.get("shots_on") and s.get("finishing") is not None and s["shots_on"] >= 2 and s["finishing"] < 35 and pos != "forward":
        weaknesses.append({"tag": "finishing", "detail": f"{s['goals']} goal{'s' * (s['goals'] != 1)} from {s['shots_on']} shots on target - the keeper is getting to them"})
    if impact and pos in ("defender", "midfielder"):
        gap = next((d["impact"] for d in impact["drivers"] if d["key"] == "other"), 0)
        if gap <= pb.POSITIONING_GAP:
            weaknesses.append({"tag": "positioning", "detail": f"Rating {abs(gap):.1f} below what their on-ball stats predict"})
    if pos == "goalkeeper" and s["saves"] >= 5 and s["conceded"] >= 3:
        strengths.append({"tag": "busy_keeper", "detail": f"{s['saves']} saves while facing {s['shots_faced']} shots on target"})
    if s.get("idle_share", 0) >= pb.IDLE_SHARE:
        weaknesses.append({"tag": "idle", "detail": f"Idle for {s['idle_share'] * 100:.0f}% of the match"})

    if s["goals"]:
        strengths.append({"tag": "goal_threat", "detail": f"{s['goals']} goal{'s' * (s['goals'] > 1)}"})
    if s["assists"] or (s.get("key_passes") or 0) >= 2:
        bits = []
        if s["assists"]:
            bits.append(f"{s['assists']} assist{'s' * (s['assists'] > 1)}")
        if s.get("key_passes"):
            bits.append(f"{s['key_passes']} key pass{'es' * (s['key_passes'] > 1)}")
        strengths.append({"tag": "creativity", "detail": ", ".join(bits)})
    if s["mom"]:
        strengths.append({"tag": "leadership", "detail": "Man of the Match"})
    if pos in ("defender", "goalkeeper") and s["clean_sheet"]:
        strengths.append({"tag": "clean_sheet", "detail": "Clean sheet"})
    if s["red_cards"]:
        weaknesses.append({"tag": "discipline", "detail": "Sent off"})

    # de-duplicate by tag, keep first detail and merge the rest
    def merge(items):
        out = {}
        for it in items:
            if it["tag"] in out:
                if it["detail"] not in out[it["tag"]]["detail"]:
                    out[it["tag"]]["detail"] += "; " + it["detail"]
            else:
                out[it["tag"]] = {**it, "title": pb.TAG_TITLES[it["tag"]]}
        return list(out.values())

    strengths, weaknesses = merge(strengths), merge(weaknesses)
    wtags = {w["tag"] for w in weaknesses}
    strengths = [x for x in strengths if x["tag"] not in wtags]
    for x in strengths:
        x["note"] = pb.STRENGTH_NOTES.get(x["tag"], "")
    for w in weaknesses:
        w["tips"] = pb.tips_for(w["tag"], pos)
    return strengths, weaknesses


def rating_band(pos, r):
    p25, p50, p75, p90 = pb.RATING_PERCENTILES[pos]
    if r >= p90:
        return "Top 10%"
    if r >= p75:
        return "Top 25%"
    if r >= p50:
        return "Above average"
    if r >= p25:
        return "Below average"
    return "Bottom 25%"


def headline(name, pos, s, strengths, weaknesses):
    r = s["rating"]
    band = rating_band(pos, r)
    tone = {"Top 10%": "Outstanding", "Top 25%": "Strong", "Above average": "Solid",
            "Below average": "Quiet", "Bottom 25%": "Tough"}[band]
    bits = []
    if strengths:
        bits.append("best at " + ", ".join(x["title"].lower() for x in strengths[:2]))
    if weaknesses:
        bits.append("work on " + ", ".join(x["title"].lower() for x in weaknesses[:2]))
    return (f"{tone} {pb.LABELS[pos].lower()} performance ({r:.1f}, {band.lower()} for the position)"
            + (" - " + "; ".join(bits) if bits else "") + ".")


# --------------------------------------------------------------- pipeline


def analyse_all(raw_matches, config):
    club_id = config["club"]["club_id"]
    seasons = config.get("seasons", [])
    roster = set(config.get("roster") or [])
    acfg = config.get("analysis", {})
    matches = [m for m in (normalise(r, club_id, seasons, roster) for r in raw_matches) if m]
    matches.sort(key=lambda m: m["ts"])

    samples = [(p["pos"], p["stats"]) for m in matches for p in m["players"] if p["stats"]["minutes"] >= 20]
    models = fit_models(samples, acfg.get("learned_model_min_samples", 40))

    history = defaultdict(list)  # player -> prior analyses
    for m in matches:
        for p in m["players"]:
            s = p["stats"]
            factor = min(max(s["minutes"], 1) / 90.0, 1.0)
            p["impact"] = rating_drivers(s, models[p["pos"]])
            strengths, weaknesses = assess(p["pos"], s, factor, p["impact"])
            p["strengths"], p["weaknesses"] = strengths, weaknesses
            p["band"] = rating_band(p["pos"], s["rating"])
            prior = history[p["name"]]
            if len(prior) >= 3:
                avg = sum(x["stats"]["rating"] for x in prior) / len(prior)
                p["vs_average"] = round(s["rating"] - avg, 2)
            p["headline"] = headline(p["name"], p["pos"], s, strengths, weaknesses)
            history[p["name"]].append({"match": m["id"], "ts": m["ts"], "pos": p["pos"], **p})
        m["players"].sort(key=lambda p: p["stats"]["rating"], reverse=True)
        m["team"] = team_totals(m["players"])

    players = {name: player_profile(name, rows, acfg) for name, rows in history.items()}
    model_info = {pos: {"learned": md["learned"], "samples": md["n"]} for pos, md in models.items()}
    return matches, players, model_info


def team_totals(players):
    t = Counter()
    for p in players:
        for k in ("goals", "assists", "shots", "shots_on", "key_passes", "passes_att", "passes_made", "tackles_att", "tackles_made", "saves"):
            t[k] += p["stats"].get(k) or 0
    return {**t, "pass_pct": _pct(t["passes_made"], t["passes_att"]), "tackle_pct": _pct(t["tackles_made"], t["tackles_att"]),
            "shot_accuracy": _pct(t["shots_on"], t["shots"])}


def _avg(rows, key):
    vals = [r["stats"][key] for r in rows if r["stats"].get(key) is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def player_profile(name, rows, acfg):
    n = len(rows)
    min_n = acfg.get("themes_min_matches", 8)
    window = acfg.get("form_window", 5)
    pos_counts = Counter(r["pos"] for r in rows)
    main_pos = pos_counts.most_common(1)[0][0]
    totals = Counter()
    for r in rows:
        for k in ("goals", "assists", "shots", "shots_on", "key_passes", "passes_att", "passes_made", "tackles_att", "tackles_made", "saves", "mom", "red_cards"):
            totals[k] += r["stats"].get(k) or 0
    averages = {k: _avg(rows, k) for k in ("rating", "pass_pct", "tackle_pct", "conversion", "shot_accuracy", "finishing",
                                           "shots", "key_passes", "passes_att", "tackles_att", "missed_tackles", "save_pct")}
    record = Counter(r["stats"]["result"] for r in rows)

    # Which actions have moved this player's rating the most, on average
    impact = defaultdict(list)
    for r in rows:
        for d in r["impact"]["drivers"]:
            impact[d["label"]].append(d["impact"])
    impact_avg = sorted(
        ({"label": k, "impact": round(sum(v) / n, 2)} for k, v in impact.items()),
        key=lambda d: d["impact"], reverse=True,
    )

    themes = build_themes(rows, main_pos, window) if n >= min_n else None
    recent = rows[-window:]
    earlier = rows[:-window]
    trend = None
    if earlier:
        trend = round(_avg(recent, "rating") - _avg(earlier, "rating"), 2)

    return {
        "name": name,
        "main_pos": main_pos,
        "positions": dict(pos_counts),
        "matches": n,
        "record": {"W": record["W"], "D": record["D"], "L": record["L"]},
        "totals": dict(totals),
        "averages": averages,
        "form": [{"match": r["match"], "ts": r["ts"], "rating": r["stats"]["rating"], "pos": r["pos"]} for r in rows],
        "trend": trend,
        "band": rating_band(main_pos, averages["rating"]),
        "impact": impact_avg,
        "themes": themes,
        "themes_progress": {"have": n, "need": min_n},
        "best": max(rows, key=lambda r: r["stats"]["rating"])["match"],
    }


def build_themes(rows, pos, window):
    n = len(rows)
    w_count, s_count = Counter(), Counter()
    w_recent = Counter()
    details = defaultdict(list)
    for i, r in enumerate(rows):
        for w in r["weaknesses"]:
            w_count[w["tag"]] += 1
            details[w["tag"]].append(w["detail"])
            if i >= n - window:
                w_recent[w["tag"]] += 1
        for s in r["strengths"]:
            s_count[s["tag"]] += 1
    recent_n = min(window, n)
    improve = []
    for tag, c in w_count.most_common():
        rate = c / n
        if rate < 0.3 or len(improve) >= 3:
            continue
        recent_rate = w_recent[tag] / recent_n
        direction = "improving" if recent_rate < rate - 0.1 else "worsening" if recent_rate > rate + 0.1 else "steady"
        improve.append({
            "tag": tag, "title": pb.TAG_TITLES[tag], "rate": round(rate * 100),
            "recent_rate": round(recent_rate * 100), "direction": direction,
            "tips": pb.tips_for(tag, pos, limit=4),
        })
    strengths = [
        {"tag": t, "title": pb.TAG_TITLES[t], "rate": round(c / n * 100), "note": pb.STRENGTH_NOTES.get(t, "")}
        for t, c in s_count.most_common() if c / n >= 0.4
    ][:3]
    return {"improve": improve, "strengths": strengths}
