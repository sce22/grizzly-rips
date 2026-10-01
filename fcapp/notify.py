"""Text-message delivery. Phone numbers and credentials come from environment
variables (GitHub Actions secrets) so they never end up in the public repo.

Option A - Twilio:        TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM, NOTIFY_PHONE
Option B - email-to-SMS:  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMS_GATEWAY_ADDRESS
The owner's number gets the text for config notify.my_player.
Other players (optional): PLAYER_SMS='{"GamerTag": "5551234567@vtext.com" or "+15551234567"}'

Email-to-text gateways cut each message at ~160 characters *including* their
own sender header, so long texts are split into numbered parts that fit.
"""
import base64
import json
import os
import smtplib
import time
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


def chunk(text, limit):
    """Split on line breaks into numbered parts of at most `limit` characters."""
    lines = text.split("\n")
    for total_guess in range(1, 20):
        parts, cur = [], ""
        budget = limit - len(f"({total_guess}/{total_guess}) ")
        for line in lines:
            while len(line) > budget:  # a single over-long line: hard wrap at a space
                cut = line.rfind(" ", 0, budget)
                cut = cut if cut > 0 else budget
                if cur:
                    parts.append(cur)
                    cur = ""
                parts.append(line[:cut])
                line = line[cut:].lstrip()
            candidate = f"{cur}\n{line}" if cur else line
            if len(candidate) > budget:
                parts.append(cur)
                cur = line
            else:
                cur = candidate
        if cur:
            parts.append(cur)
        if len(parts) <= total_guess:
            if len(parts) == 1:
                return parts
            return [f"({i}/{len(parts)}) {p}" for i, p in enumerate(parts, 1)]
    return [text[:limit]]


def _email_gateway(address, body, limit):
    parts = chunk(body, limit) if limit else [body]
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", 587))) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        for i, part in enumerate(parts):
            msg = EmailMessage()
            msg["From"] = os.environ["SMTP_USER"]
            msg["To"] = address
            msg.set_content(part)
            s.send_message(msg)
            if i < len(parts) - 1:
                time.sleep(4)  # keeps the parts arriving in order
    return len(parts)


def send(body, to=None, limit=120):
    """Send to `to` (email-gateway address or E.164 number), or to the owner."""
    to = to or os.environ.get("SMS_GATEWAY_ADDRESS") or os.environ.get("NOTIFY_PHONE")
    if not to:
        print("[notify] No recipient configured - message would have been:\n" + body)
        return None
    if "@" in to and os.environ.get("SMTP_USER"):
        n = _email_gateway(to, _ascii(body), limit)
        return f"email-gateway ({n} part{'s' * (n > 1)})"
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


def player_text(match, player, base_url, test=False):
    from .coach import text_lines
    lines = text_lines(match, player)
    if test:
        lines[0] = "[TEST] " + lines[0]
    lines[-1] += f" {base_url}#/m/{match['id']}/{urllib.parse.quote(player['name'])}"  # sign-off + link stay together
    return _ascii("\n".join(lines))


def sat_out_text(match, name, base_url):
    word = {"W": "W", "D": "D", "L": "L"}[match["result"]]
    return _ascii(f"{match['gf']}-{match['ga']} {word} vs {match['opponent']['name']}\n"
                  f"{name}, you sat this one out. Team talk:\n{base_url}#/m/{match['id']}")
