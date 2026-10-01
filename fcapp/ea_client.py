"""Client for EA's public Pro Clubs stats feed (the same data proclubs.ea.com uses).

EA fronts this API with bot protection that rejects ordinary HTTP clients, so we
use curl_cffi, which presents a real Chrome TLS fingerprint.
"""
import time

from curl_cffi import requests

BASE = "https://proclubs.ea.com/api/fc/"
HEADERS = {
    "Accept": "application/json",
    "Referer": "https://www.ea.com/",
    "Origin": "https://www.ea.com",
}
CREST_URL = (
    "https://eafc24.content.easports.com/fifa/fltOnlineAssets/"
    "24B23FDE-7835-41C2-87A2-F453DFDB2E82/2024/fcweb/crests/256x256/l{asset_id}.png"
)


class EAClient:
    def __init__(self, platform="common-gen5", retries=3):
        self.platform = platform
        self.retries = retries
        self.session = requests.Session(impersonate="chrome")

    def _get(self, path, **params):
        params.setdefault("platform", self.platform)
        last = None
        for attempt in range(self.retries):
            r = self.session.get(BASE + path, params=params, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}: {r.text[:200]}"
            time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"EA API request failed for {path}: {last}")

    def search_clubs(self, name):
        return self._get("allTimeLeaderboard/search", clubName=name)

    def club_info(self, club_id):
        return self._get("clubs/info", clubIds=club_id).get(str(club_id))

    def matches(self, club_id, match_type="leagueMatch", count=10):
        return self._get(
            "clubs/matches", clubIds=club_id, matchType=match_type, maxResultCount=count
        )

    def member_stats(self, club_id):
        return self._get("members/stats", clubId=club_id).get("members", [])


def crest_url(club_info):
    asset = (club_info or {}).get("customKit", {}).get("crestAssetId")
    return CREST_URL.format(asset_id=asset) if asset else None


def kit_hex(value):
    """EA stores kit colours as decimal RGB integers."""
    try:
        return "#{:06x}".format(int(value))
    except (TypeError, ValueError):
        return None
