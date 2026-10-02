"""FC 27 Pro Clubs league ladder, tracked by us.

EA's public stats still report the old 10-division format (and a division
number that lags), so we follow the FC 27 ladder ourselves:

  Division 5 -> 4 -> 3 -> 2 -> 1 -> Elite
  * points phase: earn the division's points target (Div 5: 7, Div 3: 12;
    others configurable in config.json league.rules.points_targets); a loss
    costs a life.
    Reaching the target promotes you (Div 5 and 4) or puts you into
    promotion matches (Div 3 and up). Running out of lives means a
    relegation match.
  * promotion matches: `promotion_matches` (4) games to reach
    `promotion_points` (10). Make it and you go up; once it's out of reach,
    you play a relegation match.
  * relegation match: win or draw to stay (back to the points phase); a
    loss drops a division.

Starting point: data/league_state.json (the "seed"), confirmed by the user and
correctable any time with Actions -> "Update league status". Every league
match after the seed moves the ladder forward.
"""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from .store import DATA, read_json

SEED_FILE = "league_state.json"
DIVISIONS = ["5", "4", "3", "2", "1", "Elite"]
DEFAULT_RULES = {
    # Confirmed: Division 5 = 7 (in-game screen), Division 3 = 12 (club). The rest are
    # best guesses until confirmed - correct them in config.json.
    "points_targets": {"5": 7, "4": 9, "3": 12, "2": 12, "1": 12, "Elite": 12},
    "lives": 3,
    "promotion_matches": 4,
    "promotion_points": 10,
    "promotion_matches_from": "3",   # divisions 3, 2 and 1 play promotion matches
    "relegation_win_needed": False,  # a draw in the relegation match keeps you up; only a loss drops you
}
PTS = {"W": 3, "D": 1, "L": 0}
TZ = ZoneInfo("America/Chicago")


def rules(config):
    return {**DEFAULT_RULES, **config.get("league", {}).get("rules", {})}


def target(d, r):
    return r["points_targets"].get(d, 12)


def div_name(d):
    return "Elite" if d == "Elite" else f"Division {d}"


def next_div(d):
    i = DIVISIONS.index(d)
    return DIVISIONS[i + 1] if i + 1 < len(DIVISIONS) else None


def prev_div(d):
    i = DIVISIONS.index(d)
    return DIVISIONS[i - 1] if i > 0 else d


def _points_phase(division, r):
    return {"division": division, "stage": "points", "points": 0, "lives": r["lives"],
            "promo_played": 0, "promo_points": 0, "promo_results": [], "phase_results": []}


def _when(ts):
    d = datetime.fromtimestamp(ts, TZ)
    return f"{d:%b} {d.day}, {d:%-I:%M %p}"


def apply(state, m, r):
    """Move the ladder forward by one league match. Returns an event dict or None."""
    res, d = m["result"], state["division"]
    score = f"{m['gf']}-{m['ga']}"
    opp = m["opponent"]["name"]
    ev = {"ts": m["ts"], "match": m["id"], "result": res, "score": score, "opp": opp, "division": d, "stage": state["stage"]}

    if state["stage"] == "points":
        state["points"] += PTS[res]
        state["phase_results"].append(res)
        if res == "L":
            state["lives"] -= 1
        goal = target(d, r)
        reached = state["points"] >= goal
        if reached and next_div(d) is None:
            ev.update(kind="target", text=f"{goal}/{goal} pts in Elite ({res} {score} vs {opp})")
            state.update(_points_phase(d, r))
        elif reached and DIVISIONS.index(d) >= DIVISIONS.index(r["promotion_matches_from"]):
            ev.update(kind="qualified", text=f"Reached {goal} pts in {div_name(d)} ({res} {score} vs {opp}). Promotion matches to {div_name(next_div(d))}")
            state.update(stage="promotion", promo_played=0, promo_points=0, promo_results=[])
        elif reached:
            nd = next_div(d)
            ev.update(kind="promoted", text=f"Promoted to {div_name(nd)} ({res} {score} vs {opp})")
            state.update(_points_phase(nd, r))
        elif state["lives"] <= 0:
            ev.update(kind="relegation_match_due", text=f"Out of lives in {div_name(d)} ({res} {score} vs {opp}). Relegation match next")
            state.update(stage="relegation")
        else:
            ev["kind"] = "points"
        return ev

    if state["stage"] == "promotion":
        state["promo_played"] += 1
        state["promo_points"] += PTS[res]
        state["promo_results"].append(res)
        left = r["promotion_matches"] - state["promo_played"]
        ev["text"] = f"Promotion match {state['promo_played']}: {res} {score} vs {opp}"
        if state["promo_points"] >= r["promotion_points"]:
            nd = next_div(d)
            ev.update(kind="promoted", text=ev["text"] + f". Promoted to {div_name(nd)}!")
            state.update(_points_phase(nd, r))
        elif state["promo_points"] + 3 * left < r["promotion_points"]:
            ev.update(kind="relegation_match_due", text=ev["text"] + ". Promotion out of reach; relegation match next")
            state.update(stage="relegation")
        else:
            ev["kind"] = "promo_match"
        return ev

    # relegation match
    stayed = res == "W" or (res == "D" and not r["relegation_win_needed"])
    if stayed:
        ev.update(kind="survived", text=f"Relegation match {'won' if res == 'W' else 'drawn'} ({score} vs {opp}). Staying in {div_name(d)}")
        state.update(_points_phase(d, r))
    else:
        pd = prev_div(d)
        ev.update(kind="relegated" if pd != d else "survived",
                  text=f"Relegation match {res} {score} vs {opp}. " + (f"Down to {div_name(pd)}" if pd != d else f"Staying in {div_name(d)}"))
        state.update(_points_phase(pd, r))
    return ev


def track(matches, config, until_ts=None):
    """Ladder state after every league match up to `until_ts` (default: now).
    Returns (state, events, seed) or (None, [], None) without a seed."""
    seed = read_json(SEED_FILE)
    if not seed:
        return None, [], None
    r = rules(config)
    state = json.loads(json.dumps(seed["state"]))
    events = list(seed.get("history", []))
    if until_ts is not None and until_ts < seed["as_of_ts"]:
        return None, [], seed
    for m in sorted(matches, key=lambda x: x["ts"]):
        if m["type"] != "leagueMatch" or m["ts"] <= seed["as_of_ts"] or (until_ts is not None and m["ts"] >= until_ts):
            continue
        events.append(apply(state, m, r))
    return state, events, seed


def describe(state, config, events=(), taken_at=None):
    """Display-ready snapshot used by the site, the Daily Summary and Coach Lasso."""
    r = rules(config)
    d = state["division"]
    nd = next_div(d)
    out = {"division": d, "division_name": div_name(d), "next_name": div_name(nd) if nd else None,
           "stage": state["stage"], "points": state["points"], "target": target(d, r),
           "target_confirmed": d in ("5", "3"),
           "lives": state["lives"], "max_lives": r["lives"], "phase_results": state.get("phase_results", []),
           "taken_at": taken_at or datetime.now(TZ).isoformat(timespec="minutes")}
    status = []
    if state["stage"] == "points":
        need = max(0, target(d, r) - state["points"])
        goal = (f"promotion matches for {div_name(nd)}" if nd and DIVISIONS.index(d) >= DIVISIONS.index(r["promotion_matches_from"])
                else f"promotion to {div_name(nd)}" if nd else "the Elite target")
        out["stage_label"] = f"{div_name(d)} · points phase"
        status.append(f"{state['points']}/{target(d, r)} pts: {need} more for {goal}")
        status.append(f"{state['lives']} of {r['lives']} lives left before a relegation match")
    elif state["stage"] == "promotion":
        played, pts = state["promo_played"], state["promo_points"]
        left = r["promotion_matches"] - played
        need = max(0, r["promotion_points"] - pts)
        wins = -(-need // 3)
        out["promo"] = {"played": played, "total": r["promotion_matches"], "points": pts, "target": r["promotion_points"],
                        "results": state["promo_results"], "left": left, "need": need, "wins_needed": wins}
        out["stage_label"] = f"Promotion matches → {div_name(nd)}"
        status.append(f"Promotion matches: {played} of {r['promotion_matches']} played ({' '.join(state['promo_results']) or 'none yet'}), {pts}/{r['promotion_points']} pts")
        status.append(f"Need {need} pts from {left} match{'es' if left != 1 else ''}: {wins} win{'s' if wins != 1 else ''}" +
                      (" (every one counts)" if wins == left else ""))
        status.append(f"Miss out and it's a relegation match to stay in {div_name(d)}")
    else:
        out["stage_label"] = f"Relegation match · {div_name(d)}"
        status.append(f"Relegation match next: a win or a draw keeps us in {div_name(d)}; a loss drops us to {div_name(prev_div(d))}")
    out["status"] = status
    if state["stage"] == "promotion":
        pr = out["promo"]
        out["spoken"] = (f"We're in {div_name(d)}, playing promotion matches for {div_name(nd)}. {pr['played']} down, {pr['left']} to go, "
                         f"and we need {pr['need']} more points, which means {pr['wins_needed']} win{'s' if pr['wins_needed'] != 1 else ''}")
    elif state["stage"] == "points":
        out["spoken"] = (f"We're in {div_name(d)} with {state['points']} of {target(d, r)} points and "
                         f"{state['lives']} li{'ves' if state['lives'] != 1 else 'fe'} left")
    else:
        out["spoken"] = f"We've got a relegation match coming to stay in {div_name(d)}, and a draw is enough"
    out["history"] = [e for e in events if e.get("kind") not in ("points",)][-8:]
    return out


def snapshot(matches, config, until_ts=None):
    state, events, _ = track(matches, config, until_ts)
    if not state:
        return None
    taken = datetime.fromtimestamp(until_ts, TZ).isoformat(timespec="minutes") if until_ts else None
    return describe(state, config, events, taken)


def write_seed(division, stage, points, lives, promo_played, promo_points, promo_results, as_of_match, history=None, note=""):
    """Save a confirmed starting point (used by the 'Update league status' form)."""
    seed = {
        "note": note,
        "as_of_ts": as_of_match["ts"], "as_of_match": as_of_match["id"],
        "set_at": datetime.now(TZ).isoformat(timespec="minutes"),
        "state": {"division": division, "stage": stage, "points": points, "lives": lives,
                  "promo_played": promo_played, "promo_points": promo_points, "promo_results": promo_results,
                  "phase_results": []},
        "history": history or [],
    }
    (DATA / SEED_FILE).write_text(json.dumps(seed, indent=1))
    return seed
