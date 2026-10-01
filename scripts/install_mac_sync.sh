#!/bin/zsh
# One-time: make this Mac run the sync every 20 minutes in the background.
DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.fcclaude.sync.plist"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.fcclaude.sync</string>
  <key>ProgramArguments</key><array><string>/bin/zsh</string><string>$DIR/scripts/sync_from_mac.sh</string></array>
  <key>StartInterval</key><integer>1200</integer>
  <key>StandardOutPath</key><string>$DIR/data/sync.log</string>
  <key>StandardErrorPath</key><string>$DIR/data/sync.log</string>
</dict></plist>
PL
launchctl unload "$PLIST" 2>/dev/null; launchctl load "$PLIST" && echo "Mac sync installed (every 20 min)."
