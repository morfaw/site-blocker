#!/bin/bash
set -e

# Downloads StevenBlack's porn-only blocklist and updates the dnsmasq blocklist
# Source: https://github.com/StevenBlack/hosts
# Run periodically: sudo bash update-adult-blocklist.sh

BLOCKLIST_FILE="/usr/local/share/blocked/adult-domains.conf"
URL="https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/porn-only/hosts"
TMPFILE=$(mktemp)

echo "Downloading adult content blocklist..."
curl -sL "$URL" -o "$TMPFILE"

echo "Converting to dnsmasq format..."
grep '^0\.0\.0\.0 ' "$TMPFILE" \
    | grep -v 'localhost' \
    | grep -v '0\.0\.0\.0 0\.0\.0\.0' \
    | awk '{print "address=/"$2"/127.0.0.1"}' \
    | sort -u > "$BLOCKLIST_FILE"

COUNT=$(wc -l < "$BLOCKLIST_FILE" | tr -d ' ')
rm -f "$TMPFILE"

# Restart dnsmasq to pick up changes
brew services restart dnsmasq 2>/dev/null || sudo brew services restart dnsmasq 2>/dev/null || true

echo ""
echo "Done! $COUNT adult domains blocked via dnsmasq."
echo "Blocklist: $BLOCKLIST_FILE"
