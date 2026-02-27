#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/rootb/Code/a17/internal-tools/outreach-tool-automation"
DAEMON_DIR="/Library/LaunchDaemons"

sudo cp "$ROOT/ops/com.a17.outreach.daemon.plist" "$DAEMON_DIR/com.a17.outreach.daemon.plist"
sudo cp "$ROOT/ops/com.a17.outreach.reset.daemon.plist" "$DAEMON_DIR/com.a17.outreach.reset.daemon.plist"

sudo launchctl unload "$DAEMON_DIR/com.a17.outreach.daemon.plist" 2>/dev/null || true
sudo launchctl unload "$DAEMON_DIR/com.a17.outreach.reset.daemon.plist" 2>/dev/null || true

sudo launchctl load "$DAEMON_DIR/com.a17.outreach.daemon.plist"
sudo launchctl load "$DAEMON_DIR/com.a17.outreach.reset.daemon.plist"

echo "Installed and loaded daemons"
