"""Push notifications through ntfy (https://ntfy.sh) - free, no accounts.

Every player gets a private channel ("topic") derived from the NTFY_SECRET
repository secret, so anyone who shows up in our matches automatically has
one. Nothing here prints a topic name: workflow logs on a public repo are
public, and anyone who knows a topic can read it.

To add someone: Actions -> "Invite a player" -> Run workflow. Their subscribe
link is pushed to *your* phone; forward it to them.
"""
import hashlib
import hmac
import json
import os
import re
import urllib.parse
import urllib.request

SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")


def enabled():
    return bool(os.environ.get("NTFY_SECRET"))


def topic_for(player_name, club_name="grizzly-rips"):
    key = os.environ["NTFY_SECRET"].encode()
    digest = hmac.new(key, player_name.lower().encode(), hashlib.sha256).hexdigest()[:10]
    who = re.sub(r"[^a-z0-9]+", "", player_name.lower())[:14] or "player"
    club = re.sub(r"[^a-z0-9]+", "-", club_name.lower()).strip("-")[:16]
    return f"{club}-{who}-{digest}"


def send(topic, title, message, click=None, actions=None, tags=None):
    body = {"topic": topic, "title": title, "message": message}
    if click:
        body["click"] = click
    if actions:
        body["actions"] = actions
    if tags:
        body["tags"] = tags
    req = urllib.request.Request(SERVER, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status == 200
    except Exception as e:  # never echo the topic
        print(f"[push] send failed: {type(e).__name__}")
        return False


RESULT_TAG = {"W": "trophy", "D": "handshake", "L": "muscle"}


def push_player(club_name, match, player, base_url):
    title, message = player["push"]["title"], player["push"]["body"]
    card = f"{base_url}#/match/{match['id']}/{urllib.parse.quote(player['name'])}"
    return send(
        topic_for(player["name"], club_name), title, message,  # no click URL: tapping opens it in ntfy
        actions=[{"action": "view", "label": "My breakdown", "url": card},
                 {"action": "view", "label": "Team talk", "url": f"{base_url}#/match/{match['id']}"}],
        tags=["soccer", RESULT_TAG[match["result"]]],
    )


def subscribe_link(topic):
    return f"{SERVER}/{topic}"

