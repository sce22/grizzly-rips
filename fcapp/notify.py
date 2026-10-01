"""Text-message delivery. Phone numbers and credentials come from environment
variables (GitHub Actions secrets) so they never end up in the public repo.

Option A - Twilio:        TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM, NOTIFY_PHONE
Option B - email-to-SMS:  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMS_GATEWAY_ADDRESS
The owner's number gets the text for config notify.my_player.
Other players (optional): PLAYER_SMS='{"GamerTag": "5551234567@vtext.com" or "+15551234567"}'

Email-to-text gateways cut each message at ~160 characters *including* their
own sender header, and drop rapid follow-ups, so each text is one short
message of at most notify.sms_max_chars (default 125).
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
    """Send to `to` (email-gateway address or E.164 number), or to the owner."""
    to = to or os.environ.get("SMS_GATEWAY_ADDRESS") or os.environ.get("NOTIFY_PHONE")
    if not to:
        print("[notify] No recipient configured - message would have been:\n" + body)
        return None
    if "@" in to and os.environ.get("SMTP_USER"):
        _email_gateway(to, _ascii(body))
        return f"email-gateway ({len(body)} chars)"
    if "@" not in to and os.environ.get("TWILIO_ACCOUNT_SID"):
        _twilio(to, body)  # Twilio joins long messages itself
        return f"twilio:{to[-4:]}"
    print("[notify] No SMS provider configured for this recipient - message would have been:\n" + body)
    return None


def recipients(config):
    """{gamertag: address} - the owner's player plus any per-player numbers."""
    out = {}
    try:
        out.update(json.loads(os.environ.get("PLAYER_SMS") or os.environ.get("PLAYER_PHONES") or "{}"))
    except json.JSONDecodeError:
        print("[notify] PLAYER_SMS is not valid JSON - ignoring it")
    me = config.get("notify", {}).get("my_player")
    owner = os.environ.get("SMS_GATEWAY_ADDRESS") or os.environ.get("NOTIFY_PHONE")
    if me and owner:
        out[me] = owner
    return out


ASCII = str.maketrans({"\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
                       "\u00b7": "-", "\u2026": "...", "\u2265": ">=", "\u2264": "<="})


def _ascii(text):
    """Email-to-text gateways mangle anything beyond plain ASCII."""
    return text.translate(ASCII).encode("ascii", "ignore").decode()


def short_link(base_url, route):
    """Phones auto-link a bare domain; dropping https:// saves 8 characters."""
    return base_url.split("://", 1)[-1] + "#/" + route


def player_text(match, player, base_url, limit=125, me=False):
    from .coach import text_paragraph
    link = short_link(base_url, "l" if me else f"l/{urllib.parse.quote(player['name'])}")
    return _ascii(f"{text_paragraph(match, player, limit - len(link) - 1)} {link}")


def sat_out_text(match, name, base_url):
    return _ascii(f"{match['result']} {match['gf']}-{match['ga']}. You sat this one out, {name}. "
                  f"Team talk: {short_link(base_url, 'm/' + match['id'])}")
