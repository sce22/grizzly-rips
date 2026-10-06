"""Full pipeline: fetch new matches -> analyse -> coach -> build site -> text new results.

    python -m fcapp.run              # one sync
    python -m fcapp.run --no-fetch   # rebuild from stored matches only
    python -m fcapp.run --no-notify  # don't send texts
    python -m fcapp.run --test-text  # text the latest match to check SMS setup

The always-on watcher (python -m fcapp.watch) calls the same functions.
"""
import argparse
import sys

from . import analysis, build_site, coach, daily, league, notify, push
from .store import (load_config, load_matches, read_json, refile, save_match,
                    write_json, write_season_summaries)


def season_of(config):
    def _season(raw):
        ours = raw.get("clubs", {}).get(str(config["club"]["club_id"]), {})
        return analysis.season_for(int(raw["timestamp"]), ours.get("season_id"), config.get("seasons", []))
    return _season


def fetch(config, client=None, with_meta=True):
    from .ea_client import EAClient, crest_url, kit_hex

    club = config["club"]
    client = client or EAClient(platform=club.get("platform", "common-gen5"))
    if with_meta:
        info = client.club_info(club["club_id"]) or {}
        kit = info.get("customKit", {})
        write_json("club_meta.json", {
            "ea_name": info.get("name"),
            "crest_url": crest_url(info),
            "stadium": kit.get("stadName"),
            "kit_colors": [c for c in (kit_hex(kit.get(f"kitColor{i}")) for i in (1, 2, 3)) if c],
        })
    season = season_of(config)
    new_ids = []
    for mtype in config.get("match_types", ["leagueMatch"]):
        for raw in client.matches(club["club_id"], mtype):
            if save_match(raw, mtype, season(raw)):
                new_ids.append(str(raw["matchId"]))
    return new_ids


def rebuild(config):
    refile(season_of(config))
    matches, players, model_info = analysis.analyse_all(load_matches(), config)
    coach.annotate(matches, players, config)
    write_json("model.json", {"matches_in_archive": len(matches), "positions": model_info})
    write_season_summaries(matches)
    build_site.build(config, matches, players, model_info)
    print(f"Built site: {len(matches)} matches, {len(players)} players")
    return matches


def send_texts(config, matches, new_ids):
    ncfg = config.get("notify", {})
    if not ncfg.get("enabled", True):
        return
    from .invite import invite_new_members
    invite_new_members(config, matches)  # first-time players: subscribe key to the owner
    by_id = {m["id"]: m for m in matches}
    if read_json("notified.json") is None:
        # Don't text the backlog EA returns on the very first sync
        write_json("notified.json", sorted(set(new_ids)))
        return
    notified = set(read_json("notified.json", []) or [])
    base = config["site"]["base_url"]
    limit = ncfg.get("sms_max_chars", 125)
    people = notify.recipients(config)
    for mid in sorted((i for i in new_ids if i in by_id), key=lambda i: by_id[i]["ts"]):
        if mid in notified:
            continue
        m = by_id[mid]
        played = {p["name"]: p for p in m["players"]}
        if push.enabled() and ncfg.get("push", True):
            for p in m["players"]:  # every player gets their own; only subscribers see it
                push.push_player(config["club"]["name"], m, p, base)
        if not ncfg.get("sms", True):
            notified.add(mid)
            continue
        for name, address in people.items():
            if name in played:
                me = name == ncfg.get("my_player")
                notify.send(notify.player_text(m, played[name], base, limit, me=me), to=address)
            elif name == ncfg.get("my_player"):
                notify.send(notify.sat_out_text(m, name, base), to=address)
        notified.add(mid)
    write_json("notified.json", sorted(notified))


def daily_due(config):
    """Cheap check (no analysis) for closed days that still need a summary."""
    return daily.due_days([{"ts": int(m["timestamp"])} for m in load_matches()], config)


def write_daily(config, client=None):
    """Write summaries for every closed day that's due, each with the league
    ladder as it stood when that day closed. Returns the new summaries."""
    matches = rebuild(config)
    cfg = daily.settings(config)
    new = []
    for day in daily.due_days(matches, config):
        table = league.snapshot(matches, config, until_ts=daily.window(day, cfg)[1].timestamp())
        summary = daily.generate(day, matches, config, table)
        daily.save(summary)
        print(f"[daily] {summary['title']}: {summary['games']} games, grade {summary['grade']}, speech by {summary['speech_by']}")
        new.append(summary)
    if new:
        rebuild(config)  # put them on the site
    return new


def push_daily(config, summary, names=None):
    """Push a summary to the given players (default: everyone who played that day)."""
    if not push.enabled():
        print("[daily] NTFY_SECRET not set - nothing sent")
        return 0
    title, body, url = daily.notification(summary, config["site"]["base_url"])
    tags = ["soccer", "trophy" if summary["score"] >= 13 else "muscle" if summary["score"] <= 6 else "handshake"]
    sent = 0
    for name in names or summary["active"]:
        ok = push.send(push.topic_for(name, config["club"]["name"]), title, body,
                       actions=[{"action": "view", "label": "Open Daily Summary", "url": url}], tags=tags)
        print(f"{name}: daily summary push {'sent' if ok else 'FAILED'}")
        sent += ok
    return sent


def latest_for(matches, name):
    return next((m for m in reversed(matches) for p in m["players"] if p["name"] == name), None)


def send_tests(config, matches, args):
    """Send each named player the notes from their own latest match."""
    names = [n.strip() for n in args.players.split(",") if n.strip()] or [config["notify"]["my_player"]]
    base, club = config["site"]["base_url"], config["club"]["name"]
    failures = 0
    for name in names:
        m = latest_for(matches, name)
        if not m:
            print(f"{name}: no stored match - check the gamertag spelling")
            failures += 1
            continue
        player = next(p for p in m["players"] if p["name"] == name)
        if push.enabled() and args.channel in ("all", "push"):
            ok = push.push_player(club, m, player, base)
            print(f"{name}: push {'sent' if ok else 'FAILED'} (their latest match: {m['gf']}-{m['ga']} vs {m['opponent']['name']})")
            failures += not ok
        if config["notify"].get("sms", True) and args.channel in ("all", "sms") and name == config["notify"].get("my_player"):
            text = notify.player_text(m, player, base, config["notify"].get("sms_max_chars", 125), me=True)
            via = notify.send(text)
            print(f"{name}: text {'sent via ' + via if via else 'not sent (no SMS provider)'}")
    if failures:
        sys.exit(1)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--no-notify", action="store_true")
    ap.add_argument("--test-text", action="store_true", help="send my latest match now, to check notifications")
    ap.add_argument("--channel", choices=["all", "push", "sms"], default="all")
    ap.add_argument("--test-daily", action="store_true", help="push the latest Daily Summary (or --date) to --players")
    ap.add_argument("--preview-daily", action="store_true", help="write today's summary so far (not saved) and push it to --players")
    ap.add_argument("--date", default="", help="YYYY-MM-DD for --test-daily / --preview-daily")
    ap.add_argument("--players", default="", help="comma-separated gamertags for --test-text (default: notify.my_player)")
    args = ap.parse_args(argv)

    config = load_config()
    if not config["club"].get("club_id"):
        sys.exit("Set club.club_id in config.json first (run: python -m fcapp.find_club \"Club Name\")")

    new_ids = [] if args.no_fetch else fetch(config)
    print(f"New matches: {len(new_ids)}")
    matches = rebuild(config)

    if args.preview_daily:
        # Tonight's summary as it stands right now, written fresh and pushed as a
        # test; nothing is saved, so the real one is still written at 11pm.
        from datetime import datetime
        cfg = daily.settings(config)
        day = datetime.fromisoformat(args.date).date() if args.date else daily.day_of(datetime.now(cfg["tz"]).timestamp(), cfg)
        table = league.snapshot(matches, config, until_ts=min(daily.window(day, cfg)[1].timestamp(), datetime.now(cfg["tz"]).timestamp()))
        summary = daily.generate(day, matches, config, table)
        summary["title"] = "TEST · " + summary["title"]
        print(f"[daily] preview {summary['date']}: grade {summary['grade']}, speech by {summary['speech_by']}, {len(summary['speech'].split())} words")
        names = [n.strip() for n in args.players.split(",") if n.strip()] or [config["notify"]["my_player"]]
        if not push_daily(config, summary, names):
            sys.exit(1)
        return
    if args.test_daily:
        summaries = daily.load_all()
        summary = next((x for x in summaries if x["date"] == args.date), None) if args.date else (summaries[-1] if summaries else None)
        if not summary:
            sys.exit("No Daily Summary saved for that date yet.")
        names = [n.strip() for n in args.players.split(",") if n.strip()] or [config["notify"]["my_player"]]
        if not push_daily(config, summary, names):
            sys.exit(1)
        return
    if args.test_text:
        send_tests(config, matches, args)
        return
    if not args.no_notify:
        send_texts(config, matches, new_ids)


if __name__ == "__main__":
    main()
