#!/bin/zsh
# Fallback if EA blocks GitHub's servers: run the sync from this Mac instead.
# Installed as a background job by scripts/install_mac_sync.sh - no terminal needed afterwards.
set -e
cd "$(dirname "$0")/.."
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
[ -f .env ] && set -a && source .env && set +a
git pull -q --rebase
.venv/bin/python -m fcapp.run
git add data docs
git diff --cached --quiet || (git commit -qm "Sync matches (Mac) $(date -u +%FT%TZ)" && git push -q)
