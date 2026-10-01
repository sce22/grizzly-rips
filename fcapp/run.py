"""Full pipeline: fetch new matches -> analyse -> build site -> text new results.

    python -m fcapp.run              # normal run (used by GitHub Actions)
    python -m fcapp.run --no-fetch   # rebuild from stored matches only
    python -m fcapp.run --no-notify  # don't send texts
    python -m fcapp.run --test-text  # text the latest match to check SMS setup
"""
import argparse
import sys

from . import analysis, build_site, notify
from .store import load_config, load_matches, read_json, save_match, write_json


def fetch(config):
    from .ea_client import EAClient, crest_url, kit_hex

    club = config["club"]
    client = EAClient(platform=club.get("platform", "common-gen5"))
    info = client.club_info(club["club_id"]) or {}
    kit = info.get("customKit", {})
    write_json("club_meta.json", {
        "ea_name": info.get("name"),
        "crest_url": crest_url(info),
        "stadium": kit.get("stadName"),
        "kit_colors": [c for c in (kit_hex(kit.get(f"kitColor{i}")) for i in (1, 2, 3)) if c],
    })
    new_ids = []
    for mtype in config.get("match_types", ["leagueMatch"]):
        for raw in client.matches(club["club_id"], mtype):
            if save_match(raw, mtype):
                new_ids.append(str(raw["matchId"]))
    return new_ids


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

    matches, players, model_info = analysis.analyse_all(load_matches(), config)
    build_site.build(config, matches, players, model_info)
    print(f"Built site: {len(matches)} matches, {len(players)} players")

    if args.test_text:
        if not matches:
            sys.exit("No matches stored yet - nothing to send.")
        sent = notify.send("[TEST] " + notify.match_text(config["club"]["name"], matches[-1], config["site"]["base_url"]))
        if not sent:
            sys.exit("Test text not sent: no SMS provider is configured. Check the repository secrets.")
        print(f"Test text sent via {sent}")
        return
    if args.no_notify or not config.get("notify", {}).get("enabled", True):
        return
    by_id = {m["id"]: m for m in matches}
    first_run = read_json("notified.json") is None
    notified = set(read_json("notified.json", []) or [])
    if first_run:
        # Don't text the backlog EA returns on the very first sync
        write_json("notified.json", sorted(set(new_ids)))
        return
    new_ids = sorted((i for i in new_ids if i in by_id), key=lambda i: by_id[i]["ts"])
    base = config["site"]["base_url"]
    name = config["club"]["name"]
    phones = notify.player_phones() if config["notify"].get("per_player_texts") else {}
    for mid in new_ids:
        m = by_id.get(mid)
        if not m or mid in notified:
            continue
        notify.send(notify.match_text(name, m, base))
        for p in m["players"]:
            if p["name"] in phones:
                notify.send(notify.player_text(name, m, p, base), to=phones[p["name"]])
        notified.add(mid)
    write_json("notified.json", sorted(notified))


if __name__ == "__main__":
    main()
