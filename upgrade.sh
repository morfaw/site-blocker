#!/bin/bash
set -e

echo "=== Upgrading site blocker (adding HTTPS support) ==="

# 1. Stop existing server
launchctl unload /Library/LaunchDaemons/com.local.blocked-sites.plist 2>/dev/null || true
# Kill any lingering process on port 80
lsof -ti :80 | xargs kill -9 2>/dev/null || true

# 2. Copy updated files
cp /tmp/blocked/server.py /usr/local/share/blocked/
cp /tmp/blocked/index.html /usr/local/share/blocked/

# 3. Restart service
launchctl load /Library/LaunchDaemons/com.local.blocked-sites.plist

# 4. Wait for server to start and generate certs
echo "Waiting for server to generate certificates..."
sleep 3

# 5. Verify
if curl -sk https://127.0.0.1/ | grep -q "blocked" 2>/dev/null; then
    echo ""
    echo "HTTPS is working! Blocked sites will now show the custom page"
    echo "even when the browser forces HTTPS."
else
    echo ""
    echo "Checking HTTP..."
    if curl -s http://127.0.0.1/ | grep -q "blocked" 2>/dev/null; then
        echo "HTTP works. HTTPS may need a moment — try visiting a blocked site."
    else
        echo "Server may still be starting. Check: sudo cat /usr/local/share/blocked/error.log"
    fi
fi
