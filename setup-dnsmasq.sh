#!/bin/bash
set -e

echo "=== Setting up dnsmasq for adult content blocking ==="

# 1. Install dnsmasq
if ! command -v dnsmasq &>/dev/null; then
    echo "Installing dnsmasq via Homebrew..."
    sudo -u "$SUDO_USER" brew install dnsmasq
fi

DNSMASQ_DIR="/opt/homebrew/etc"
BLOCKLIST_DIR="/usr/local/share/blocked"
BLOCKLIST_FILE="$BLOCKLIST_DIR/adult-domains.conf"

# 2. Download and convert blocklist to dnsmasq format
echo "Downloading adult content blocklist..."
TMPFILE=$(mktemp)
curl -sL "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/porn-only/hosts" -o "$TMPFILE"

echo "Converting to dnsmasq format..."
grep '^0\.0\.0\.0 ' "$TMPFILE" \
    | grep -v 'localhost' \
    | grep -v '0\.0\.0\.0 0\.0\.0\.0' \
    | awk '{print "address=/"$2"/127.0.0.1"}' \
    | sort -u > "$BLOCKLIST_FILE"

COUNT=$(wc -l < "$BLOCKLIST_FILE" | tr -d ' ')
echo "Converted $COUNT domains."
rm -f "$TMPFILE"

# 3. Configure dnsmasq
echo "Configuring dnsmasq..."
cat > "$DNSMASQ_DIR/dnsmasq.conf" << 'EOF'
# Listen only on localhost
listen-address=127.0.0.1
port=53

# Upstream DNS servers
server=8.8.8.8
server=8.8.4.4
server=1.1.1.1

# Adult content blocklist
conf-file=/usr/local/share/blocked/adult-domains.conf

# Performance
cache-size=10000
neg-ttl=3600

# Don't read /etc/resolv.conf (we ARE the resolver)
no-resolv

# Don't read /etc/hosts (site-blocker handles that via its own server)
no-hosts

# Log nothing (privacy)
log-facility=/dev/null
EOF

# 4. Remove old adult blocklist from /etc/hosts if present
if grep -q "# -- ADULT CONTENT BLOCKLIST --" /etc/hosts; then
    echo "Removing old adult blocklist from /etc/hosts..."
    sed -i.bak '/# -- ADULT CONTENT BLOCKLIST --/,/# -- END ADULT CONTENT BLOCKLIST --/d' /etc/hosts
fi

# 5. Start dnsmasq
echo "Starting dnsmasq..."
sudo brew services restart dnsmasq 2>/dev/null || true

# 6. Set DNS to localhost on all active network interfaces
echo "Configuring macOS to use local DNS..."
for iface in $(networksetup -listallnetworkservices | tail -n +2 | grep -v '^\*'); do
    networksetup -setdnsservers "$iface" 127.0.0.1 2>/dev/null || true
done

# 7. Flush DNS cache
dscacheutil -flushcache
killall -HUP mDNSResponder 2>/dev/null || true

echo ""
echo "Done! dnsmasq is running with $COUNT adult domains blocked."
echo ""
echo "Blocklist file: $BLOCKLIST_FILE"
echo "dnsmasq config: $DNSMASQ_DIR/dnsmasq.conf"
echo "Update blocklist: sudo bash /usr/local/share/blocked/update-adult-blocklist.sh"
echo "Check status: sudo brew services list | grep dnsmasq"
echo ""
echo "Your distraction blocks (news, YouTube timers) still use /etc/hosts + the block page."
echo "Adult content blocking uses dnsmasq for performance (hash lookups, not file scanning)."
