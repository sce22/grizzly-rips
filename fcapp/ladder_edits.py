"""Ladder edits made in the app (the gear on the ladder card).

The site can't write to GitHub itself, so it posts the edit as a small JSON
message to a dedicated ntfy topic (config league.edit_topic). The watcher
checks that topic every minute, applies new edits with set_league.apply_status
(as of the newest league match), and rebuilds. Later matches then move the
ladder forward with the usual rules.

The topic name is in the public site, so anyone with the app can edit the
ladder - which is the intent. Every edit is validated and recorded in the
ladder history.
"""
import json
import urllib.request

from . import league
from .store import read_json, write_json

STATE = "ladder_edits.json"


def fetch_new(topic, since):
    url = f"https://ntfy.sh/{topic}/json?poll=1&since={since}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            lines = r.read().decode().splitlines()
    except Exception as e:
        print(f"[ladder] couldn't check for app edits ({type(e).__name__})")
        return []
    events = [json.loads(x) for x in lines if x.strip()]
    return [e for e in events if e.get("event") == "message"]


def validate(edit, r):
    d = str(edit.get("division", ""))
    stage = edit.get("stage")
    if d not in league.DIVISIONS or stage not in ("points", "promotion", "relegation"):
        return None
    out = {"division": d, "stage": stage}
    if stage == "points":
        out["points"] = max(0, min(99, int(edit.get("points", 0))))
        out["lives"] = max(0, min(r["lives"], int(edit.get("lives", r["lives"]))))
    if stage == "promotion":
        games, _ = league.series(d, r)
        res = [x for x in edit.get("promo_results", []) if x in ("W", "D", "L")]
        out["promo_results"] = res[: (games or 0) - 1] if games else []
    if edit.get("target") not in (None, "") and d != "Elite":
        out["target"] = max(1, min(60, int(edit["target"])))
    return out


def process(config):
    """Apply any new edits. Returns the number applied."""
    from .set_league import apply_status
    topic = config.get("league", {}).get("edit_topic")
    if not topic:
        return 0
    state = read_json(STATE) or {"since": "12h"}
    msgs = fetch_new(topic, state["since"])
    applied = 0
    for m in msgs:
        state["since"] = m["id"]
        try:
            edit = validate(json.loads(m.get("message", "")), league.rules(config))
        except (ValueError, TypeError):
            edit = None
        if not edit:
            print(f"[ladder] ignored an invalid edit ({m['id']})")
            continue
        desc = apply_status(config, edit["division"], edit["stage"], edit.get("points"), edit.get("lives"),
                            edit.get("promo_results", []), "Edited in the app", edit.get("target"))
        print(f"[ladder] applied app edit: {desc}")
        applied += 1
    if msgs or "since" not in (read_json(STATE) or {}):
        write_json(STATE, state)
    return applied
