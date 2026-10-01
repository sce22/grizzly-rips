"""Send subscribe links for players' private notification channels to the owner.

    python -m fcapp.invite                 # every player seen in our matches
    python -m fcapp.invite "GamerTag"      # one player (works before their first match too)

The links go to the owner's own ntfy channel (notify.my_player), never to the
console - workflow logs on a public repo are public.
"""
import sys

from . import push
from .store import load_config, load_matches


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
        topic = push.topic_for(name, club)
        msg = (f"Forward this to {name}:\n\n"
               f"1. Install the free ntfy app (App Store / Google Play)\n"
               f"2. Tap + and subscribe to:\n{topic}\n\n"
               f"After every match you'll get your own notes from Coach Lasso.")
        push.send(push.topic_for(me, club), f"Invite for {name}", msg,
                  click=push.subscribe_link(topic), tags=["envelope"])
    print(f"Sent {len(names)} invite(s) to the owner's channel.")


if __name__ == "__main__":
    main()
