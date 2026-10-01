"""Full pipeline: fetch new matches -> analyse -> coach -> build site -> text new results.

    python -m fcapp.run              # one sync
    python -m fcapp.run --no-fetch   # rebuild from stored matches only
    python -m fcapp.run --no-notify  # don't send texts
    python -m fcapp.run --test-text  # text the latest match to check SMS setup

The always-on watcher (python -m fcapp.watch) calls the same functions.
"""
import argparse
import sys

from . import analysis, build_site, coach, notify
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
    write_season_summaries(matches)
    build_site.build(config, matches, players, model_info)
    print(f"Built site: {len(matches)} matches, {len(players)} players")
    return matches


def send_texts(config, matches, new_ids):
    ncfg = config.get("notify", {})
    if not ncfg.get("enabled", True):
        return
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
        for name, address in people.items():
            if name in played:
                me = name == ncfg.get("my_player")
                notify.send(notify.player_text(m, played[name], base, limit, me=me), to=address)
            elif name == ncfg.get("my_player"):
                notify.send(notify.sat_out_text(m, name, base), to=address)
        notified.add(mid)
    write_json("notified.json", sorted(notified))


def latest_for(matches, name):
    return next((m for m in reversed(matches) for p in m["players"] if p["name"] == name), None)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--no-notify", action="store_true")
    ap.add_argument("--test-text", action="store_true", help="text the latest match now, to check SMS setup")
    args = ap.parse_args(argv)

    config = load_config()
    if not config["club"].get("club_id"):
        sys.exit("Set club.club_id in config.json first (run: python -m fcapp.find_club \"Club Name\")")

    new_ids = [] if args.no_fetch else fetch(config)
    print(f"New matches: {len(new_ids)}")
    matches = rebuild(config)

    if args.test_text:
        if not matches:
            sys.exit("No matches stored yet - nothing to send.")
        me = config.get("notify", {}).get("my_player")
        m = latest_for(matches, me) if me else None
        if not m:
            sys.exit(f"No stored match includes notify.my_player ({me!r}) - set it in config.json.")
        player = next(p for p in m["players"] if p["name"] == me)
        text = notify.player_text(m, player, config["site"]["base_url"], config["notify"].get("sms_max_chars", 125), me=True)
        print(f"{len(text)} chars: {text}")
        sent = notify.send(text)
        if not sent:
            sys.exit("Test text not sent: no SMS provider is configured. Check the repository secrets.")
        print(f"Test text sent via {sent}")
        return
    if not args.no_notify:
        send_texts(config, matches, new_ids)


if __name__ == "__main__":
    main()
