"""Always-on watcher: checks EA every minute and texts as soon as a match lands.

    python -m fcapp.watch --minutes 330 --interval 60

GitHub Actions restarts it every few hours (a job can run at most 6 hours).
After each new match it rebuilds the site, pushes it, waits for the page to go
live, and then sends the text, so the link works when you tap it. It exits
early if new code is pushed so the next run picks it up.
"""
import argparse
import subprocess
import time
import urllib.request

from .ea_client import EAClient
from .run import fetch, rebuild, send_texts
from .store import load_config

BOT = "fc-sync-bot"


def git(*args, check=True):
    return subprocess.run(["git", *args], check=check, capture_output=True, text=True).stdout.strip()


def commit_and_push(message):
    git("add", "data", "docs")
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        return False
    git("commit", "-q", "-m", message)
    for _ in range(3):
        git("pull", "-q", "--rebase", "origin", "main", check=False)
        if subprocess.run(["git", "push", "-q", "origin", "HEAD:main"]).returncode == 0:
            return True
        time.sleep(5)
    print("[watch] push failed after 3 attempts")
    return False


def code_changed_upstream():
    git("fetch", "-q", "origin", "main", check=False)
    authors = git("log", "HEAD..origin/main", "--format=%an", check=False).split()
    return any(a != BOT for a in authors)


def wait_until_live(url, timeout=150):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(url + f"?t={int(time.time())}", timeout=10) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(10)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=330)
    ap.add_argument("--interval", type=int, default=60)
    args = ap.parse_args()

    end = time.time() + args.minutes * 60
    client = None
    last_meta = last_upstream = 0.0
    while time.time() < end:
        config = load_config()
        try:
            client = client or EAClient(platform=config["club"].get("platform", "common-gen5"))
            refresh_meta = time.time() - last_meta > 3600
            new_ids = fetch(config, client, with_meta=refresh_meta)
            if refresh_meta:
                last_meta = time.time()
        except Exception as e:  # EA hiccup - try again next tick
            print(f"[watch] fetch failed: {e}")
            client = None
            time.sleep(args.interval)
            continue

        if new_ids:
            print(f"[watch] {len(new_ids)} new match(es): {', '.join(new_ids)}")
            matches = rebuild(config)
            commit_and_push(f"Match synced {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
            latest = max(new_ids, key=lambda i: next((m["ts"] for m in matches if m["id"] == i), 0))
            wait_until_live(config["site"]["base_url"] + f"data/matches/{latest}.json")
            send_texts(config, matches, new_ids)
            commit_and_push("Record texts sent")
        elif refresh_meta:
            commit_and_push("Refresh club info")

        if time.time() - last_upstream > 600:
            last_upstream = time.time()
            if code_changed_upstream():
                print("[watch] new code pushed - exiting so the next run uses it")
                return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
