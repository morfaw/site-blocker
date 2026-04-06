# Site Blocker

A minimal, self-hosted website blocker for macOS. Redirects distracting sites to a motivational block page with daily time budgets for sites you want to limit (not fully block).

## Features

- **Permanent blocking** — sites redirect to a dark, minimal page with rotating focus quotes
- **Timed sites** — daily time budgets (e.g. 30 min/day for YouTube) with session-based access
- **Auto-start** — runs as a launchd service, survives reboots
- **One-way UI** — you can add blocks from the web page, but removing requires `sudo nano /etc/hosts`
- **No dependencies** — just Python 3 (built into macOS) and `/etc/hosts`

## How it works

1. Blocked domains point to `127.0.0.1` via `/etc/hosts`
2. A Python HTTP server on port 80 serves the block page
3. Timed sites start blocked each day; start a session from the page to temporarily unblock
4. A background thread re-blocks timed sites when sessions expire

## Install

```bash
sudo bash install.sh
```

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
| launchd plist | `/Library/LaunchDaemons/com.local.blocked-sites.plist` |

## Uninstall

```bash
sudo launchctl unload /Library/LaunchDaemons/com.local.blocked-sites.plist
sudo rm -rf /usr/local/share/blocked
sudo rm /Library/LaunchDaemons/com.local.blocked-sites.plist
# Then remove the "BLOCKED SITES" section from /etc/hosts
sudo nano /etc/hosts
```
