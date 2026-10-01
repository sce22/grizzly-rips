"""Text-message delivery. Phone numbers and credentials come from environment
variables (GitHub Actions secrets) so they never end up in the public repo.

Option A - Twilio:        TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM, NOTIFY_PHONE
Option B - email-to-SMS:  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMS_GATEWAY_ADDRESS
Per-player texts (optional): PLAYER_PHONES='{"GamerTag": "+15551234567"}'
"""
import base64
import json
import os
import smtplib
import urllib.parse
import urllib.request
from email.message import EmailMessage


def _twilio(to, body):
    sid, token = os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"]
    data = urllib.parse.urlencode({"To": to, "From": os.environ["TWILIO_FROM"], "Body": body}).encode()
    req = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", data=data
    )
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{sid}:{token}".encode()).decode())
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def _email_gateway(address, body):
    msg = EmailMessage()
    msg["From"] = os.environ["SMTP_USER"]
    msg["To"] = address
    msg.set_content(body)
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", 587))) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        s.send_message(msg)


def send(body, to=None):
    """Send to `to` (E.164 number) or the owner's configured number."""
    if os.environ.get("TWILIO_ACCOUNT_SID"):
        target = to or os.environ["NOTIFY_PHONE"]
        _twilio(target, body)
        return f"twilio:{target[-4:]}"
    if os.environ.get("SMS_GATEWAY_ADDRESS") and not to:
        _email_gateway(os.environ["SMS_GATEWAY_ADDRESS"], body)
        return "email-gateway"
    print("[notify] No SMS provider configured - message would have been:\n" + body)
    return None


def player_phones():
    try:
        return json.loads(os.environ.get("PLAYER_PHONES", "{}"))
    except json.JSONDecodeError:
        return {}


def match_text(club_name, match, base_url):
    top = match["players"][0] if match["players"] else None
    score = f"{match['gf']}-{match['ga']}"
    word = {"W": "WIN", "D": "DRAW", "L": "LOSS"}[match["result"]]
    lines = [f"{club_name}: {word} {score} vs {match['opponent']['name']}"]
    if top:
        lines.append(f"Top rated: {top['name']} {top['stats']['rating']:.1f}")
    lines.append(f"Player breakdowns: {base_url}#/match/{match['id']}")
    return "\n".join(lines)


def player_text(club_name, match, player, base_url):
    s = player["stats"]
    work = player["weaknesses"][0]["title"] if player["weaknesses"] else "keep it up"
    return (
        f"{club_name} vs {match['opponent']['name']} ({match['gf']}-{match['ga']})\n"
        f"Your rating: {s['rating']:.1f}. Focus: {work}\n"
        f"Your breakdown: {base_url}#/match/{match['id']}/{urllib.parse.quote(player['name'])}"
    )
