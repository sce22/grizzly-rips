"""Set the league ladder's starting point (Actions -> "Update league status").

    python -m fcapp.set_league --division 3 --stage promotion --promo-results D

Everything not given is derived: points-phase points default to 0, lives to
full, promotion points from the results. The state applies as of our most
recent league match; later matches move it forward automatically.
"""
import argparse

from . import analysis, league
from .store import load_config, load_matches, read_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--division", required=True, choices=league.DIVISIONS)
    ap.add_argument("--stage", required=True, choices=["points", "promotion", "relegation"])
    ap.add_argument("--points", type=int, default=None, help="points-phase points (default 0, or the target if in promotion matches)")
    ap.add_argument("--lives", type=int, default=None)
    ap.add_argument("--promo-results", default="", help="promotion match results so far, e.g. 'D W'")
    ap.add_argument("--note", default="Set from the Update league status form")
    args = ap.parse_args()

    config = load_config()
    r = league.rules(config)
    matches, _, _ = analysis.analyse_all(load_matches(), config)
    latest = max((m for m in matches if m["type"] == "leagueMatch"), key=lambda m: m["ts"])
    results = [x for x in args.promo_results.upper().replace(",", " ").split() if x in ("W", "D", "L")]
    points = args.points if args.points is not None else (league.target(args.division, r) if args.stage == "promotion" else 0)
    lives = args.lives if args.lives is not None else r["lives"]
    old = read_json(league.SEED_FILE) or {}
    _, events, _ = league.track(matches, config) if old else (None, [], None)
    history = [e for e in events if e.get("kind") not in ("points",)][-20:] + [{
        "ts": latest["ts"], "kind": "manual",
        "text": f"Status set: {league.div_name(args.division)}, {args.stage} stage" +
                (f", promotion results {' '.join(results)}" if results else "") + f" ({args.note})"}]
    league.write_seed(args.division, args.stage, points, lives, len(results), sum(league.PTS[x] for x in results),
                      results, latest, history, args.note)
    print(f"League status set: {league.div_name(args.division)}, {args.stage}, as of the {latest['gf']}-{latest['ga']} vs {latest['opponent']['name']}")


if __name__ == "__main__":
    main()
