"""Send subscribe links for players' private notification channels to the owner.

    python -m fcapp.invite                 # every player seen in our matches
    python -m fcapp.invite "GamerTag"      # one player (works before their first match too)

The links go to the owner's own ntfy channel (notify.my_player), never to the
console - workflow logs on a public repo are public.
"""
import sys

from . import push
from .store import load_config, load_matches, read_json, write_json


def send_invite(config, name):
    """Push one player's subscribe key to the owner's channel, ready to forward."""
    club, me = config["club"]["name"], config["notify"]["my_player"]
    topic = push.topic_for(name, club)
    msg = (f"Forward this to {name}:\n\n"
           f"1. Install the free ntfy app (App Store / Google Play)\n"
           f"2. Tap + and subscribe to:\n{topic}\n\n"
           f"After every match you'll get your own notes from Coach Lasso.")
    return push.send(push.topic_for(me, club), f"New member: invite for {name}", msg,
                     click=push.subscribe_link(topic), tags=["envelope"])


def invite_new_members(config, matches):
    """Invite anyone who has just played for us for the first time. Known
    members are kept in data/members.json; the first run only records them."""
    me = config["notify"]["my_player"]
    seen = sorted({p["name"] for m in matches for p in m["players"]})
    known = read_json("members.json")
    if known is None:
        write_json("members.json", seen)
        return []
    new = [n for n in seen if n not in known and n != me]
    sent = [n for n in new if push.enabled() and send_invite(config, n)]
    if new:
        write_json("members.json", sorted(set(known) | set(seen)))
    for n in new:
        print(f"[invite] new member {n}: {'invite sent to owner' if n in sent else 'not sent (no NTFY_SECRET)'}")
    return new


def main():
    if not push.enabled():
        sys.exit("NTFY_SECRET is not set.")
    config = load_config()
    club, me = config["club"]["name"], config["notify"]["my_player"]
    cid = str(config["club"]["club_id"])
    if len(sys.argv) > 1 and sys.argv[1].strip():
        names = [sys.argv[1].strip()]
    else:
        names = sorted({p["playername"] for m in load_matches() for p in m.get("players", {}).get(cid, {}).values()} - {me})
    for name in names:
        send_invite(config, name)
    print(f"Sent {len(names)} invite(s) to the owner's channel.")


if __name__ == "__main__":
    main()
