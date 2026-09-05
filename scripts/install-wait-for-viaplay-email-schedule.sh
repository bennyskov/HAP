#!/bin/sh
set -eu

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
LABEL="com.bennyskov.strm.viaplay-email"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$PLIST_DIR/$LABEL.plist"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SCRIPT_PATH="$PROJECT_ROOT/scripts/run-viaplay-email-poller.sh"

mkdir -p "$PLIST_DIR"

cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$SCRIPT_PATH</string>
    <string>--json</string>
  </array>
  <key>StartInterval</key>
  <integer>30</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$PROJECT_ROOT/logs/viaplay-email-poller.out.log</string>
  <key>StandardErrorPath</key>
  <string>$PROJECT_ROOT/logs/viaplay-email-poller.err.log</string>
</dict>
</plist>
EOF

mkdir -p "$PROJECT_ROOT/logs"

launchctl bootout "gui/$(id -u)" "$PLIST_FILE" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_FILE"
launchctl enable "gui/$(id -u)/$LABEL"

echo "Installed $LABEL to run every 30 seconds."
