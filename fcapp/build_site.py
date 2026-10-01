"""Builds the static mobile site into docs/ (served by GitHub Pages)."""
import json
import shutil
from datetime import datetime, timezone

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
        "seasons": [s["name"] for s in config.get("seasons", [])],
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
                {"name": p["name"], "pos": p["main_pos"], "matches": p["matches"],
                 "rating": p["averages"]["rating"], "trend": p["trend"],
                 "goals": p["totals"].get("goals", 0), "assists": p["totals"].get("assists", 0)}
                for p in players.values()
            ),
            key=lambda p: -p["matches"],
        ),
    }
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
    (out / "index.html").write_text(html)


def slug(name):
    return "".join(c if c.isalnum() else "_" for c in name).lower()
