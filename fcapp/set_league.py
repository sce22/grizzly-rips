"""Set the league ladder's starting point (Actions -> "Update league status").

    python -m fcapp.set_league --division 3 --stage promotion --promo-results D

Everything not given is derived: points-phase points default to 0, lives to
full, promotion wins from the results.

The status you enter is what the game shows *now*, so it applies as of the most
recent league match EA knows about (asked live, so a match our watcher hasn't
saved yet can't be counted twice). Every league match after that moves it
forward automatically, and the ladder history carries over.
"""
import argparse

from . import analysis, league
from .store import load_config, load_matches, read_json


def apply_status(config, division, stage, points=None, lives=None, promo_results=(), note="", target=None):
    """Make the given status the ladder's new starting point, as of the newest
    league match EA knows about. Optionally update this division's points
    target. Returns a short description."""
    import json
    from .store import ROOT
    if target is not None and division != "Elite":
        cfg_path = ROOT / "config.json"
        cfg = json.loads(cfg_path.read_text())
        cfg.setdefault("league", {}).setdefault("rules", {}).setdefault("points_targets", {})[division] = int(target)
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
        config = cfg
    r = league.rules(config)
    matches, _, _ = analysis.analyse_all(load_matches(), config)
    latest = max((m for m in matches if m["type"] == "leagueMatch"), key=lambda m: m["ts"])
    try:  # EA may already have a match the watcher hasn't saved yet
        from .ea_client import EAClient
        live = EAClient(platform=config["club"].get("platform", "common-gen5")).matches(config["club"]["club_id"], "leagueMatch")
        newest = max(live, key=lambda m: int(m["timestamp"]), default=None)
        if newest and int(newest["timestamp"]) > latest["ts"]:
            ours = newest["clubs"][str(config["club"]["club_id"])]
            opp = next(v for k, v in newest["clubs"].items() if k != str(config["club"]["club_id"]))
            latest = {"id": str(newest["matchId"]), "ts": int(newest["timestamp"]), "gf": int(ours["goals"]),
                      "ga": int(ours["goalsAgainst"]), "opponent": {"name": opp.get("details", {}).get("name", "Opponent")}}
    except Exception as e:
        print(f"[league] couldn't check EA for newer matches ({type(e).__name__}); using our archive")
    results = [x for x in promo_results if x in ("W", "D", "L")]
    points = points if points is not None else ((league.target(division, r) or 0) if stage == "promotion" else 0)
    lives = r["lives"] if lives is None else max(0, min(r["lives"], int(lives)))
    old = read_json(league.SEED_FILE) or {}
    _, events, _ = league.track(matches, config) if old else (None, [], None)
    desc = f"{league.div_name(division)}, {stage} stage" + (f", promotion results {' '.join(results)}" if results else "")
    history = [e for e in events if e.get("kind") not in ("points",)][-20:] + [{"ts": latest["ts"], "kind": "manual", "text": f"Status: {desc}"}]
    league.write_seed(division, stage, int(points), lives, results, latest, history, note)
    return f"{desc}, as of the {latest['gf']}-{latest['ga']} vs {latest['opponent']['name']}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--division", required=True, choices=league.DIVISIONS)
    ap.add_argument("--stage", required=True, choices=["points", "promotion", "relegation"])
    ap.add_argument("--points", type=int, default=None, help="points-phase points (default 0, or the target if in promotion matches)")
    ap.add_argument("--lives", type=int, default=None)
    ap.add_argument("--promo-results", default="", help="promotion match results so far, e.g. 'D W'")
    ap.add_argument("--note", default="Set from the Update league status form")
    args = ap.parse_args()

    results = [x for x in args.promo_results.upper().replace(",", " ").split() if x in ("W", "D", "L")]
    print("League status set: " + apply_status(load_config(), args.division, args.stage, args.points, args.lives, results, args.note))


if __name__ == "__main__":
    main()
