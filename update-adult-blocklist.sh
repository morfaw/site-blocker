#!/bin/bash
set -e

# Downloads StevenBlack's porn-only blocklist and adds it to /etc/hosts
# Source: https://github.com/StevenBlack/hosts
# Run periodically to get updates: sudo bash update-adult-blocklist.sh

HOSTS="/etc/hosts"
MARKER_START="# -- ADULT CONTENT BLOCKLIST --"
MARKER_END="# -- END ADULT CONTENT BLOCKLIST --"
URL="https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/porn-only/hosts"
TMPFILE=$(mktemp)

echo "Downloading adult content blocklist..."
curl -sL "$URL" -o "$TMPFILE"

# Extract just the 0.0.0.0 domain lines (skip localhost, comments, blanks)
DOMAINS=$(grep '^0\.0\.0\.0 ' "$TMPFILE" | grep -v 'localhost' | grep -v '0\.0\.0\.0 0\.0\.0\.0' | awk '{print $2}' | sort -u)
COUNT=$(echo "$DOMAINS" | wc -l | tr -d ' ')

echo "Found $COUNT adult domains to block."

# Remove old adult blocklist section if it exists
if grep -q "$MARKER_START" "$HOSTS"; then
    echo "Removing old blocklist..."
    sed -i.bak "/$MARKER_START/,/$MARKER_END/d" "$HOSTS"
fi

# Append new blocklist
echo "" >> "$HOSTS"
echo "$MARKER_START" >> "$HOSTS"
echo "# Source: StevenBlack/hosts (porn-only)" >> "$HOSTS"
echo "# Updated: $(date '+%Y-%m-%d')" >> "$HOSTS"
echo "# Domains: $COUNT" >> "$HOSTS"
echo "$DOMAINS" | while read -r domain; do
    echo "127.0.0.1   $domain" >> "$HOSTS"
done
echo "$MARKER_END" >> "$HOSTS"

# Flush DNS
dscacheutil -flushcache
killall -HUP mDNSResponder 2>/dev/null || true

rm -f "$TMPFILE"

echo ""
echo "Done! $COUNT adult domains blocked."
echo "To update, run: sudo bash /usr/local/share/blocked/update-adult-blocklist.sh"
echo "To remove, edit /etc/hosts and delete the ADULT CONTENT BLOCKLIST section."
