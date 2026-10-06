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


# All-time leaderboard columns, most important first: (key, label, how, scope)
# scope "all" = every match ever played (EA's all-time member totals plus our
# archive); "tracked" = only counted since our archive began, because EA keeps
# no per-match detail from before then.
LEADERBOARD = [
    ("rating", "Avg rating", "avg", "all"), ("matches", "MP", "sum", "all"), ("goals", "Goals", "sum", "all"),
    ("assists", "Assists", "sum", "all"), ("ga", "G+A", "sum", "all"), ("mom", "MOTM", "sum", "all"),
    ("win_pct", "Win %", "pct", "all"), ("ga_pm", "G+A / match", "avg", "all"), ("conversion", "Conversion %", "pct", "all"),
    ("passes_made", "Passes done", "sum", "all"), ("pass_pct", "Pass %", "pct", "all"),
    ("tackles_made", "Tackles won", "sum", "all"), ("tackle_pct", "Tackle %", "pct", "all"),
    ("perfect", "Perfect games", "sum", "tracked"), ("key_passes", "Key passes", "sum", "tracked"), ("shots", "Shots", "sum", "tracked"),
    ("shots_on", "On target", "sum", "tracked"), ("shot_acc", "Shot acc %", "pct", "tracked"),
    ("passes_att", "Passes tried", "sum", "tracked"), ("tackles_att", "Tackles tried", "sum", "tracked"),
    ("best", "Best rating", "max", "tracked"), ("W", "W", "sum", "tracked"), ("D", "D", "sum", "tracked"), ("L", "L", "sum", "tracked"),
    ("minutes", "Minutes", "sum", "tracked"), ("red_cards", "Red cards", "sum", "all"), ("rage_quits", "Rage quits", "sum", "tracked"),
]


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def leaderboard(matches, ea_members=None):
    """Every player's all-time numbers: EA's career totals for this club (every
    match ever played, before and after our archive began) where EA has them,
    and our own archive for everything EA doesn't total up."""
    acc = {}
    for m in matches:
        for p in m["players"]:
            s = p["stats"]
            a = acc.setdefault(p["name"], {"name": p["name"], "pos": {}, "ratings": [], "raw": [], **{k: 0 for k in (
                "goals", "assists", "mom", "perfect", "key_passes", "shots", "shots_on", "passes_made", "passes_att",
                "tackles_made", "tackles_att", "W", "D", "L", "minutes", "red_cards", "rage_quits")}})
            a["ratings"].append(s["rating"])
            a["raw"].append(s.get("raw_rating", s["rating"]))
            a["pos"][p["pos"]] = a["pos"].get(p["pos"], 0) + 1
            a[m["result"]] += 1
            for k, src in (("goals", "goals"), ("assists", "assists"), ("mom", "mom"), ("perfect", "perfect"), ("key_passes", "key_passes"),
                           ("shots", "shots"), ("shots_on", "shots_on"), ("passes_made", "passes_made"), ("passes_att", "passes_att"),
                           ("tackles_made", "tackles_made"), ("tackles_att", "tackles_att"),
                           ("minutes", "minutes"), ("red_cards", "red_cards"), ("rage_quits", "rage_quit")):
                a[k] += s.get(src) or 0
    ea = {x.get("name"): x for x in (ea_members or [])}
    pct = lambda n, d: round(n / d * 100, 1) if d else None
    rows = []
    for name in set(acc) | set(ea):
        a = acc.get(name) or {"name": name, "pos": {}, "ratings": [], "raw": [], **{k: 0 for k in (
            "goals", "assists", "mom", "perfect", "key_passes", "shots", "shots_on", "passes_made", "passes_att",
            "tackles_made", "tackles_att", "W", "D", "L", "minutes", "red_cards", "rage_quits")}}
        e = ea.get(name, {})
        n_arch = len(a["ratings"])
        n_ea = int(_num(e.get("gamesPlayed")) or 0)
        n = max(n_arch, n_ea)
        if not n:
            continue
        before = n - n_arch  # matches EA counts that happened before our archive
        tot = lambda key, ea_key: max(a[key], int(_num(e.get(ea_key)) or 0))
        goals, assists = tot("goals", "goals"), tot("assists", "assists")
        # Rating: EA's all-time average covers every match; swap in our 5.0
        # floor for rage quits we know about
        if before > 0 and _num(e.get("ratingAve")) is not None:
            all_raw = _num(e["ratingAve"]) * n
            rating = (all_raw - sum(a["raw"]) + sum(a["ratings"])) / n
        else:
            rating = sum(a["ratings"]) / n_arch
        ea_rate = lambda key, own: _num(e.get(key)) if before > 0 and _num(e.get(key)) is not None else own
        pos = max(a["pos"], key=a["pos"].get) if a["pos"] else (e.get("favoritePosition") or "midfielder")
        rows.append({
            "name": name, "pos": pos, "matches": n, "matches_tracked": n_arch,
            "rating": round(rating, 2), "best": max(a["ratings"]) if a["ratings"] else None,
            "goals": goals, "assists": assists, "ga": goals + assists, "ga_pm": round((goals + assists) / n, 2),
            "mom": tot("mom", "manOfTheMatch"), "passes_made": tot("passes_made", "passesMade"),
            "tackles_made": tot("tackles_made", "tacklesMade"), "red_cards": tot("red_cards", "redCards"),
            "win_pct": ea_rate("winRate", pct(a["W"], n_arch)), "conversion": ea_rate("shotSuccessRate", pct(a["goals"], a["shots"])),
            "pass_pct": ea_rate("passSuccessRate", pct(a["passes_made"], a["passes_att"])),
            "tackle_pct": ea_rate("tackleSuccessRate", pct(a["tackles_made"], a["tackles_att"])),
            "shot_acc": pct(a["shots_on"], a["shots"]),
            **{k: a[k] for k in ("perfect", "key_passes", "shots", "shots_on", "passes_att", "tackles_att",
                                 "W", "D", "L", "minutes", "rage_quits")},
        })
    first = min((m["ts"] for m in matches), default=None)
    since = datetime.fromtimestamp(first, timezone.utc).astimezone().strftime("%b %-d, %Y") if first else None
    return {"columns": [{"key": k, "label": l, "how": h, "scope": sc} for k, l, h, sc in LEADERBOARD],
            "tracked_since": since, "rows": sorted(rows, key=lambda r: -r["rating"])}


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
    from .store import read_json
    lb = leaderboard(matches, (read_json("member_stats.json") or {}).get("members"))
    index["leaderboard"] = lb
    by_name = {r["name"]: r for r in lb["rows"]}
    for p in index["players"]:  # squad cards show the same all-time numbers
        r = by_name.get(p["name"])
        if r:
            p.update(all_rating=r["rating"], all_matches=r["matches"], all_goals=r["goals"], all_assists=r["assists"])
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
