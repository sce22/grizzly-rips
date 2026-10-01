"""Match repository on disk: one JSON file per match, filed by season, never
overwritten or deleted.

    data/seasons/season-01/matches/<matchId>.json
    data/seasons/season-01/summary.json      (record, dates, match list)

EA only returns a club's 10 most recent matches per match type, so the
watcher polls every minute; everything it has ever seen is kept here.
"""
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SEASONS_DIR = DATA / "seasons"


def load_config():
    return json.loads((ROOT / "config.json").read_text())


def season_key(season_name):
    """'Season 1 · Sep 17 – Oct 22' -> 'season-01'; other names are slugified."""
    m = re.match(r"Season (\d+)", season_name)
    if m:
        return f"season-{int(m.group(1)):02d}"
    return re.sub(r"[^a-z0-9]+", "-", season_name.lower()).strip("-") or "unsorted"


def _match_dir(season_name):
    return SEASONS_DIR / season_key(season_name) / "matches"


def known_ids():
    return {p.stem for p in DATA.rglob("matches/*.json")}


def save_match(raw, match_type, season_name):
    """Store a raw EA match in its season. Returns True if it was new."""
    if str(raw["matchId"]) in known_ids():
        return False
    raw = dict(raw)
    raw.pop("timeAgo", None)
    raw["_matchType"] = match_type
    raw["_collectedAt"] = datetime.now(timezone.utc).isoformat()
    path = _match_dir(season_name) / f"{raw['matchId']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=1))
    return True


def refile(season_of):
    """Move any match stored outside its season folder (older flat layout, or a
    changed season schedule). `season_of(raw) -> season name`."""
    moved = 0
    for path in list(DATA.rglob("matches/*.json")):
        raw = json.loads(path.read_text())
        target = _match_dir(season_of(raw)) / path.name
        if path != target:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), target)
            moved += 1
    for d in sorted(DATA.rglob("*"), reverse=True):  # tidy folders left empty
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    return moved


def write_season_summaries(matches):
    """Per-season record + match list, alongside the season's raw matches."""
    by_season = {}
    for m in matches:
        by_season.setdefault(m["season"], []).append(m)
    for name, ms in by_season.items():
        rec = {"W": 0, "D": 0, "L": 0}
        for m in ms:
            rec[m["result"]] += 1
        summary = {
            "season": name,
            "matches_played": len(ms),
            "record": rec,
            "goals_for": sum(m["gf"] for m in ms),
            "goals_against": sum(m["ga"] for m in ms),
            "first_match": ms[0]["date"],
            "last_match": ms[-1]["date"],
            "matches": [{"id": m["id"], "date": m["date"], "result": m["result"], "score": f"{m['gf']}-{m['ga']}",
                         "opponent": m["opponent"]["name"]} for m in ms],
        }
        path = SEASONS_DIR / season_key(name) / "summary.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=1, ensure_ascii=False))


def load_matches():
    matches = [json.loads(p.read_text()) for p in DATA.rglob("matches/*.json")]
    return sorted(matches, key=lambda m: int(m["timestamp"]))


def read_json(name, default=None):
    path = DATA / name
    return json.loads(path.read_text()) if path.exists() else default


def write_json(name, obj):
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / name).write_text(json.dumps(obj, indent=1))
