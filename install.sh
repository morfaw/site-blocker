#!/bin/bash
set -e

echo "=== Installing site blocker ==="

# 1. Copy files
mkdir -p /usr/local/share/blocked
cp /tmp/blocked/index.html /usr/local/share/blocked/
cp /tmp/blocked/server.py /usr/local/share/blocked/
cp /tmp/blocked/timers.json /usr/local/share/blocked/

# 2. Install launchd service
cp /tmp/blocked/com.local.blocked-sites.plist /Library/LaunchDaemons/
chmod 644 /Library/LaunchDaemons/com.local.blocked-sites.plist
launchctl load /Library/LaunchDaemons/com.local.blocked-sites.plist

# 3. Add blocked domains to /etc/hosts
MARKER="# -- BLOCKED SITES --"
if ! grep -q "$MARKER" /etc/hosts; then
    cat >> /etc/hosts << 'EOF'

# -- BLOCKED SITES --
127.0.0.1   news.google.com
127.0.0.1   news.google.de
127.0.0.1   m.youtube.com
127.0.0.1   www.youtube.com
127.0.0.1   youtube.com
127.0.0.1   news.ycombinator.com
127.0.0.1   www.tagesschau.de
127.0.0.1   tagesschau.de
127.0.0.1   www.spiegel.de
127.0.0.1   spiegel.de
127.0.0.1   www.bild.de
127.0.0.1   bild.de
127.0.0.1   www.zeit.de
127.0.0.1   zeit.de
127.0.0.1   www.faz.net
127.0.0.1   faz.net
127.0.0.1   www.welt.de
127.0.0.1   welt.de
127.0.0.1   www.n-tv.de
127.0.0.1   n-tv.de
127.0.0.1   www.focus.de
127.0.0.1   focus.de
127.0.0.1   www.stern.de
127.0.0.1   stern.de
127.0.0.1   www.bbc.com
127.0.0.1   bbc.com
127.0.0.1   www.cnn.com
127.0.0.1   cnn.com
127.0.0.1   www.reddit.com
127.0.0.1   reddit.com
127.0.0.1   old.reddit.com
127.0.0.1   www.buzzfeed.com
127.0.0.1   buzzfeed.com
127.0.0.1   www.9gag.com
127.0.0.1   9gag.com
# -- END BLOCKED SITES --
EOF
fi

# 4. Flush DNS cache
dscacheutil -flushcache
killall -HUP mDNSResponder 2>/dev/null || true

echo ""
echo "Done! Here's what's set up:"
echo ""
echo "TIMED (30 min/day):"
echo "  youtube.com, www.youtube.com, m.youtube.com"
echo ""
echo "PERMANENTLY BLOCKED:"
echo "  News:    news.google.com/de, Hacker News, Tagesschau, Spiegel, Bild,"
echo "           Zeit, FAZ, Welt, n-tv, Focus, Stern, BBC, CNN"
echo "  Other:   Reddit, BuzzFeed, 9GAG"
echo ""
echo "Manage at: http://127.0.0.1 (or visit any blocked site)"
echo "Edit timers: /usr/local/share/blocked/timers.json"
echo "Edit page: /usr/local/share/blocked/index.html"
echo "Unblock sites: sudo nano /etc/hosts"
echo "Uninstall: sudo launchctl unload /Library/LaunchDaemons/com.local.blocked-sites.plist"
