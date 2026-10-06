"""Builds the static mobile site into docs/ (served by GitHub Pages)."""
import json
import shutil
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .store import ROOT, read_json

SITE_SRC = ROOT / "site"
OUT = ROOT / "docs"


def _dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(",", ":")))


def branding(config, out, meta=None):
    club = config["club"]
    meta = meta if meta is not None else (read_json("club_meta.json", {}) or {})
    colors = {}
    auto = meta.get("kit_colors", [])
    defaults = ["#0b1f3a", "#e5b73b", "#ffffff"]
    for i, key in enumerate(("primary", "secondary", "accent")):
        val = club.get("colors", {}).get(key, "auto")
        colors[key] = val if val and val != "auto" else (auto[i] if i < len(auto) else defaults[i])

    logo = club.get("logo", "auto")
    logo_url = None
    if logo and logo != "auto":
        src = ROOT / logo
        if src.exists():
            (out / "assets").mkdir(parents=True, exist_ok=True)
            shutil.copy(src, out / "assets" / ("logo" + src.suffix))
            logo_url = "assets/logo" + src.suffix
        elif logo.startswith("http"):
            logo_url = logo
    if not logo_url:
        logo_url = meta.get("crest_url")
    return {
        "name": club["name"],
        "short_name": club.get("short_name") or club["name"],
        "colors": colors,
        "logo": logo_url,
        "stadium": meta.get("stadium"),
    }


# All-time leaderboard columns, most important first: (key, label, how)
# Totals are sums; rates are worked out from the totals (e.g. pass % = all
# completed / all attempted), not averages of per-match percentages.
LEADERBOARD = [
    ("rating", "Avg rating", "avg"), ("matches", "MP", "sum"), ("goals", "Goals", "sum"), ("assists", "Assists", "sum"),
    ("ga", "G+A", "sum"), ("mom", "MOTM", "sum"), ("win_pct", "Win %", "pct"), ("perfect", "Perfect games", "sum"),
    ("ga_pm", "G+A / match", "avg"), ("key_passes", "Key passes", "sum"), ("shots", "Shots", "sum"),
    ("shots_on", "On target", "sum"), ("shot_acc", "Shot acc %", "pct"), ("conversion", "Conversion %", "pct"),
    ("passes_made", "Passes done", "sum"), ("passes_att", "Passes tried", "sum"), ("pass_pct", "Pass %", "pct"),
    ("tackles_made", "Tackles won", "sum"), ("tackles_att", "Tackles tried", "sum"), ("tackle_pct", "Tackle %", "pct"),
    ("best", "Best rating", "max"), ("W", "W", "sum"), ("D", "D", "sum"), ("L", "L", "sum"),
    ("minutes", "Minutes", "sum"), ("red_cards", "Red cards", "sum"), ("rage_quits", "Rage quits", "sum"),
]


def leaderboard(matches):
    """Every player's all-time numbers (all match types, every season)."""
    acc = {}
    for m in matches:
        for p in m["players"]:
            s = p["stats"]
            a = acc.setdefault(p["name"], {"name": p["name"], "pos": {}, "ratings": [], **{k: 0 for k in (
                "goals", "assists", "mom", "perfect", "key_passes", "shots", "shots_on", "passes_made", "passes_att",
                "tackles_made", "tackles_att", "saves", "shots_faced", "clean_sheets", "W", "D", "L", "minutes",
                "red_cards", "rage_quits")}})
            a["ratings"].append(s["rating"])
            a["pos"][p["pos"]] = a["pos"].get(p["pos"], 0) + 1
            a[m["result"]] += 1
            for k, src in (("goals", "goals"), ("assists", "assists"), ("mom", "mom"), ("perfect", "perfect"), ("key_passes", "key_passes"),
                           ("shots", "shots"), ("shots_on", "shots_on"), ("passes_made", "passes_made"), ("passes_att", "passes_att"),
                           ("tackles_made", "tackles_made"), ("tackles_att", "tackles_att"), ("saves", "saves"), ("shots_faced", "shots_faced"),
                           ("minutes", "minutes"), ("red_cards", "red_cards"), ("rage_quits", "rage_quit")):
                a[k] += s.get(src) or 0
            a["clean_sheets"] += s.get("clean_sheet") or 0
    pct = lambda n, d: round(n / d * 100, 1) if d else None
    rows = []
    for a in acc.values():
        n = len(a["ratings"])
        rows.append({
            "name": a["name"], "pos": max(a["pos"], key=a["pos"].get), "matches": n,
            "rating": round(sum(a["ratings"]) / n, 2), "best": max(a["ratings"]),
            "ga": a["goals"] + a["assists"], "ga_pm": round((a["goals"] + a["assists"]) / n, 2),
            "win_pct": pct(a["W"], n), "shot_acc": pct(a["shots_on"], a["shots"]), "conversion": pct(a["goals"], a["shots"]),
            "pass_pct": pct(a["passes_made"], a["passes_att"]), "tackle_pct": pct(a["tackles_made"], a["tackles_att"]),
            "save_pct": pct(a["saves"], a["shots_faced"]) if a["saves"] else None,  # keepers only
            **{k: a[k] for k in ("goals", "assists", "mom", "perfect", "key_passes", "shots", "shots_on", "passes_made", "passes_att",
                                 "tackles_made", "tackles_att", "saves", "clean_sheets", "W", "D", "L", "minutes", "red_cards", "rage_quits")},
        })
    return {"columns": [{"key": k, "label": l, "how": h} for k, l, h in LEADERBOARD],
            "rows": sorted(rows, key=lambda r: -r["rating"])}


def build(config, matches, players, model_info, out=OUT, meta=None):
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(SITE_SRC, out)
    (out / ".nojekyll").write_text("")
    brand = branding(config, out, meta)

    index = {
        "club": brand,
        "generated": datetime.now(timezone.utc).isoformat(),
        "model": model_info,
        "themes_min_matches": config.get("analysis", {}).get("themes_min_matches", 8),
        "season_starts": season_starts(config.get("seasons"), matches),
        "my_player": config.get("notify", {}).get("my_player"),
        "matches": [
            {
                "id": m["id"], "ts": m["ts"], "season": m["season"], "type": m["type"],
                "result": m["result"], "gf": m["gf"], "ga": m["ga"], "opponent": m["opponent"]["name"],
                "top": {"name": m["players"][0]["name"], "rating": m["players"][0]["stats"]["rating"]} if m["players"] else None,
            }
            for m in reversed(matches)
        ],
        "players": sorted(
            (
                {"name": p["name"], "pos": p["main_pos"], "matches": p["matches"], "latest": p["form"][-1]["match"],
                 "rating": p["averages"]["rating"], "trend": p["trend"],
                 "goals": p["totals"].get("goals", 0), "assists": p["totals"].get("assists", 0)}
                for p in players.values()
            ),
            key=lambda p: -p["matches"],
        ),
    }
    index["leaderboard"] = leaderboard(matches)
    from .league import snapshot as league_snapshot
    index["league"] = league_snapshot(matches, config)
    from .league import rules as league_rules
    lr = league_rules(config)
    index["league_rules"] = {"points_targets": lr["points_targets"], "promotion": lr["promotion"], "lives": lr["lives"]}
    index["league_edit_topic"] = config.get("league", {}).get("edit_topic")
    from .daily import load_all as load_daily
    summaries = load_daily()
    index["daily"] = [{"date": d["date"], "label": d["label"], "grade": d["grade"], "games": d["games"],
                       "record": d["record"], "gf": d["gf"], "ga": d["ga"]} for d in summaries]
    for d in summaries:
        _dump(out / "data" / "daily" / f"{d['date']}.json", {k: v for k, v in d.items() if k not in ("score", "phrases")})
    _dump(out / "data" / "index.json", index)
    for m in matches:
        for p in m["players"]:
            p.pop("event_codes", None)
        _dump(out / "data" / "matches" / f"{m['id']}.json", m)
    for p in players.values():
        _dump(out / "data" / "players" / f"{slug(p['name'])}.json", p)

    # Theme colour + name baked into the manifest so "Add to Home Screen" is branded
    manifest = {
        "name": brand["name"], "short_name": brand["short_name"][:12],
        "start_url": ".", "display": "standalone",
        "background_color": brand["colors"]["primary"], "theme_color": brand["colors"]["primary"],
        "icons": [{"src": brand["logo"], "sizes": "256x256", "type": "image/png"}] if brand["logo"] else [],
    }
    _dump(out / "manifest.json", manifest)
    html = (out / "index.html").read_text()
    html = html.replace("{{CLUB_NAME}}", brand["name"]).replace("{{THEME_COLOR}}", brand["colors"]["primary"])
    # Cache-bust: browsers (and home-screen apps) otherwise keep old app files
    # for a while after an update.
    import hashlib
    ver = hashlib.sha1((out / "app.js").read_bytes() + (out / "styles.css").read_bytes()).hexdigest()[:10]
    html = html.replace('src="app.js"', f'src="app.js?v={ver}"').replace('href="styles.css"', f'href="styles.css?v={ver}"')
    (out / "index.html").write_text(html)


def season_starts(seasons, matches):
    """Calendar markers: the Thursday each season starts, as shown in its label."""
    if isinstance(seasons, dict):
        tz = ZoneInfo(seasons.get("timezone", "UTC"))
        start = datetime.fromisoformat(seasons["rollover"]).replace(tzinfo=tz)
        length = timedelta(weeks=seasons.get("length_weeks", 5))
        last = max([datetime.now(tz)] + [datetime.fromtimestamp(m["ts"], tz) for m in matches])
        out, n = [], 0
        while start + n * length <= last + length:
            day = start + n * length - timedelta(days=1)
            out.append({"date": day.strftime("%Y-%m-%d"), "short": f"S{seasons.get('first_number', 1) + n}"})
            n += 1
        return out
    return [{"date": s["start"], "short": s["name"][:3]} for s in seasons or []]


def slug(name):
    return "".join(c if c.isalnum() else "_" for c in name).lower()
