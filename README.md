# Site Blocker

A minimal, self-hosted website blocker for macOS. Redirects distracting sites to a motivational block page with daily time budgets for sites you want to limit (not fully block).

## Features

- **Permanent blocking** — sites redirect to a dark, minimal page with rotating focus quotes
- **Timed sites** — daily time budgets (e.g. 30 min/day for YouTube) with session-based access
- **Auto-start** — runs as a launchd service, survives reboots
- **One-way UI** — you can add blocks from the web page, but removing requires `sudo nano /etc/hosts`
- **HTTPS support** — auto-generates a local CA and certs so browsers don't show "Not Secure" warnings
- **Parental controls** — optional adult content blocklist (76k+ domains via dnsmasq, from [StevenBlack/hosts](https://github.com/StevenBlack/hosts))
- **No dependencies** — Python 3 (built into macOS), OpenSSL, and `/etc/hosts`. Optional: dnsmasq (via Homebrew) for large blocklists

## How it works

1. Blocked domains point to `127.0.0.1` via `/etc/hosts`
2. A Python HTTP/HTTPS server on ports 80 and 443 serves the block page
3. A local CA certificate is generated and trusted in macOS Keychain — browsers accept the HTTPS cert
4. Timed sites start blocked each day; start a session from the page to temporarily unblock
5. A background thread re-blocks timed sites when sessions expire
6. Server certs auto-regenerate when new domains are added (to include them as SANs)

## Install

```bash
sudo bash install.sh
```

After install, trust the CA cert (if not done automatically):

```bash
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain /usr/local/share/blocked/certs/ca.crt
```

Then restart Chrome (Cmd+Q and reopen) for it to pick up the new trusted CA.

## Upgrade

```bash
sudo bash upgrade.sh
```

## Adult Content Blocklist (via dnsmasq)

Optionally block ~76k adult/porn domains using dnsmasq (a lightweight local DNS server). This is much faster than putting them in `/etc/hosts`, which would cause system-wide performance issues.

```bash
# First-time setup: installs dnsmasq, downloads blocklist, configures DNS
sudo bash setup-dnsmasq.sh

# Update the blocklist later
sudo bash update-adult-blocklist.sh
```

To remove: `brew services stop dnsmasq` and restore your DNS settings in System Settings > Network.

## Usage

- Visit any blocked site → see the block page
- Or go to `http://127.0.0.1` directly
- Add permanent blocks from the page
- Start timed sessions from the page
- Remove blocks manually: `sudo nano /etc/hosts`

## Files (after install)

| File | Location |
|------|----------|
| Block page | `/usr/local/share/blocked/index.html` |
| Server | `/usr/local/share/blocked/server.py` |
| Timer state | `/usr/local/share/blocked/timers.json` |
| CA cert | `/usr/local/share/blocked/certs/ca.crt` |
| Server cert | `/usr/local/share/blocked/certs/server.crt` |
| dnsmasq blocklist | `/usr/local/share/blocked/adult-domains.conf` |
| dnsmasq config | `/opt/homebrew/etc/dnsmasq.conf` |
| launchd plist | `/Library/LaunchDaemons/com.local.blocked-sites.plist` |

## Uninstall

```bash
sudo launchctl unload /Library/LaunchDaemons/com.local.blocked-sites.plist
sudo rm -rf /usr/local/share/blocked
sudo rm /Library/LaunchDaemons/com.local.blocked-sites.plist
# Then remove the "BLOCKED SITES" section from /etc/hosts
sudo nano /etc/hosts
```
