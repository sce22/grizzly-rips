"""Builds a preview site from made-up matches so you can see the app before
connecting a real club:  python -m fcapp.demo   ->  open demo/index.html
"""
import random
from datetime import datetime, timedelta, timezone

from . import analysis, build_site
from .store import ROOT, load_config

CLUB_ID = "1000"
OPP_NAMES = ["Sunday League XI", "Kebab FC", "Rovers United", "Nutmeg Athletic", "Backline Bandits",
             "Top Bin Town", "Tiki Taka FC", "Offside Trap", "Park Rangers", "Late Run CF"]
# name, pos, skill profile (pass accuracy, tackle success, finishing, involvement)
SQUAD = [
    ("KeeperKev", "goalkeeper", dict(p=0.82, t=0.5, f=0.1, inv=0.4, save=0.72)),
    ("WallByTheSea", "defender", dict(p=0.91, t=0.62, f=0.1, inv=1.0)),
    ("SlideTackleSam", "defender", dict(p=0.8, t=0.33, f=0.1, inv=0.9)),
    ("MetronomeMo", "midfielder", dict(p=0.9, t=0.45, f=0.25, inv=1.3)),
    ("CaptainChaos", "midfielder", dict(p=0.76, t=0.52, f=0.3, inv=1.0)),
    ("PoacherPete", "forward", dict(p=0.72, t=0.3, f=0.42, inv=0.6)),
]


def fake_match(i, ts, rng):
    gf, ga = rng.choice([0, 1, 1, 2, 2, 3, 3, 4]), rng.choice([0, 1, 1, 2, 2, 3])
    players = {}
    goals_left, assists_left = gf, max(gf - rng.randint(0, 1), 0)
    for n, (name, pos, sk) in enumerate(SQUAD):
        if rng.random() < 0.12 and pos != "goalkeeper":
            continue  # didn't play this one
        p_att = int(rng.gauss(28 * sk["inv"], 6)) if pos != "goalkeeper" else rng.randint(6, 14)
        p_made = sum(rng.random() < sk["p"] for _ in range(max(p_att, 0)))
        t_att = max(int(rng.gauss({"defender": 7, "midfielder": 5, "forward": 2}.get(pos, 0), 2)), 0)
        t_made = sum(rng.random() < sk["t"] for _ in range(t_att))
        shots = max(int(rng.gauss({"forward": 5, "midfielder": 2, "defender": 0.5}.get(pos, 0), 1.5)), 0)
        goals = 0
        if goals_left and shots and pos != "goalkeeper":
            goals = min(goals_left, sum(rng.random() < sk["f"] for _ in range(shots)))
            goals_left -= goals
        assists = 1 if assists_left and pos in ("midfielder", "forward") and rng.random() < 0.5 else 0
        assists_left -= assists
        shots_on = min(shots, goals + sum(rng.random() < 0.55 for _ in range(shots - goals)))
        key_passes = assists + sum(rng.random() < 0.05 * sk["inv"] for _ in range(max(p_att, 0) // 3)) if pos != "goalkeeper" else 0
        saves = rng.randint(1, 6) if pos == "goalkeeper" else 0
        red = 1 if name == "SlideTackleSam" and rng.random() < 0.12 else 0
        w = analysis.BASELINE[pos]
        acts = {"goals": goals, "assists": assists, "key_passes": key_passes, "shots_on": shots_on,
                "shots_off": shots - shots_on, "passes_made": p_made, "passes_missed": p_att - p_made,
                "tackles_made": t_made, "missed_tackles": t_att - t_made, "saves": saves, "conceded": ga,
                "clean_sheet": int(ga == 0), "red_cards": red, "result_val": (gf > ga) - (gf < ga)}
        rating = w["_intercept"] + sum(w.get(k, 0) * v for k, v in acts.items()) + rng.gauss(0, 0.35)
        players[f"9{n}"] = {
            "playername": name, "pos": pos, "rating": f"{min(max(rating, 3.0), 10.0):.2f}",
            "goals": goals, "assists": assists, "shots": shots, "passattempts": p_att, "passesmade": p_made,
            "tackleattempts": t_att, "tacklesmade": t_made, "saves": saves, "goalsconceded": ga,
            "cleansheetsany": 1 if ga == 0 else 0, "redcards": red, "mom": 0, "secondsPlayed": 5400,
            "match_event_aggregate_0": f"214:{goals},217:{shots_on},218:{shots - shots_on},114:{key_passes},11:{assists}",
            "realtimegame": 960, "realtimeidle": rng.choice([0, 0, 0, 4, 12]),
        }
    if players:
        best = max(players.values(), key=lambda p: float(p["rating"]))
        best["mom"] = 1
    res = dict(wins=int(gf > ga), losses=int(gf < ga), ties=int(gf == ga))
    return {
        "matchId": str(700000 + i), "timestamp": str(ts), "_matchType": "leagueMatch",
        "clubs": {
            CLUB_ID: {"goals": gf, "goalsAgainst": ga, "season_id": "0", **res},
            "2000": {"goals": ga, "goalsAgainst": gf, "details": {"name": OPP_NAMES[i % len(OPP_NAMES)]}},
        },
        "players": {CLUB_ID: players, "2000": {}},
    }


def main():
    rng = random.Random(27)
    config = load_config()
    config["club"] = {**config["club"], "club_id": CLUB_ID}
    if config["club"]["name"] == "YOUR CLUB NAME":
        config["club"]["name"] = "Demo United FC"
    config["seasons"] = [
        {"name": "Early Access", "start": "2026-08-01", "end": "2026-09-14"},
        {"name": "Season 1", "start": "2026-09-15", "end": "2026-12-31"},
    ]
    start = datetime(2026, 8, 20, 20, tzinfo=timezone.utc)
    raws = [fake_match(i, int((start + timedelta(days=i * 2.8, hours=rng.random())).timestamp()), rng) for i in range(15)]
    matches, players, model = analysis.analyse_all(raws, config)
    meta = {"kit_colors": ["#0b2545", "#e0a526", "#ffffff"], "crest_url": None, "stadium": "Demo Park"}
    build_site.build(config, matches, players, model, out=ROOT / "demo", meta=meta)
    print(f"Demo built: {ROOT / 'demo' / 'index.html'}")


if __name__ == "__main__":
    main()
