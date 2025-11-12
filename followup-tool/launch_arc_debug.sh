#!/bin/bash
# Launch Arc browser with remote debugging enabled for Playwright

echo "🔧 Setting up Arc browser with remote debugging..."

# Close Arc if it's already running (so we can relaunch with debugging)
if pgrep -x "Arc" > /dev/null; then
    echo "   Closing existing Arc instances..."
    killall Arc 2>/dev/null || true
    sleep 2
fi

# Launch Arc with remote debugging
echo "   Launching Arc with remote debugging on port 9222..."
open -a Arc --args --remote-debugging-port=9222

# Wait for Arc to start
echo "   Waiting for Arc to start..."
sleep 5

# Check if Arc is listening on port 9222
if lsof -i :9222 > /dev/null 2>&1; then
    echo "✓ Arc browser is running with remote debugging enabled!"
    echo ""
    echo "You can now run:"
    echo "   python3 followup_gmail.py --profile pretti --arc"
else
    echo "⚠ Warning: Arc might not be listening on port 9222 yet."
    echo "   Try waiting a few more seconds, or manually open Arc and check."
    echo ""
    echo "To verify, run: lsof -i :9222"
fi

