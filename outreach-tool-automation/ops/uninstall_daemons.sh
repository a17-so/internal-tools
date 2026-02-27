#!/usr/bin/env bash
set -euo pipefail

DAEMON_DIR="/Library/LaunchDaemons"

sudo launchctl unload "$DAEMON_DIR/com.a17.outreach.daemon.plist" 2>/dev/null || true
sudo launchctl unload "$DAEMON_DIR/com.a17.outreach.reset.daemon.plist" 2>/dev/null || true

sudo rm -f "$DAEMON_DIR/com.a17.outreach.daemon.plist"
sudo rm -f "$DAEMON_DIR/com.a17.outreach.reset.daemon.plist"

echo "Uninstalled daemons"
