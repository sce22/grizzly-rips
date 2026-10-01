"""Match repository on disk: one JSON file per match, never overwritten.

EA only returns a club's most recent handful of matches, so the collector must
run regularly; everything it has ever seen is kept here permanently.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MATCH_DIR = DATA / "matches"


def load_config():
    return json.loads((ROOT / "config.json").read_text())


def save_match(raw, match_type):
    """Store a raw EA match. Returns True if it was new."""
    MATCH_DIR.mkdir(parents=True, exist_ok=True)
    path = MATCH_DIR / f"{raw['matchId']}.json"
    if path.exists():
        return False
    raw = dict(raw)
    raw.pop("timeAgo", None)
    raw["_matchType"] = match_type
    raw["_collectedAt"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(raw, indent=1))
    return True


def load_matches():
    if not MATCH_DIR.exists():
        return []
    matches = [json.loads(p.read_text()) for p in MATCH_DIR.glob("*.json")]
    return sorted(matches, key=lambda m: int(m["timestamp"]))


def read_json(name, default=None):
    path = DATA / name
    return json.loads(path.read_text()) if path.exists() else default


def write_json(name, obj):
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / name).write_text(json.dumps(obj, indent=1))
