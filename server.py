#!/usr/bin/env python3
"""HTTP server that serves the blocked page, manages blocked sites, and enforces daily timers."""

import http.server
import json
import os
import re
import ssl
import subprocess
import threading
import time
from datetime import datetime, date

BLOCKED_DIR = "/usr/local/share/blocked"
HOSTS_FILE = "/etc/hosts"
TIMERS_FILE = os.path.join(BLOCKED_DIR, "timers.json")
CERTS_DIR = os.path.join(BLOCKED_DIR, "certs")
CA_KEY = os.path.join(CERTS_DIR, "ca.key")
CA_CERT = os.path.join(CERTS_DIR, "ca.crt")
SERVER_KEY = os.path.join(CERTS_DIR, "server.key")
SERVER_CERT = os.path.join(CERTS_DIR, "server.crt")
MARKER_START = "# -- BLOCKED SITES --"
MARKER_END = "# -- END BLOCKED SITES --"

timers_lock = threading.Lock()


# --- /etc/hosts management ---

def read_hosts():
    """Read /etc/hosts and return (pre, blocked_domains, post)."""
    with open(HOSTS_FILE, "r") as f:
        content = f.read()
    if MARKER_START not in content:
        return content.rstrip("\n"), [], ""
    pre, rest = content.split(MARKER_START, 1)
    if MARKER_END in rest:
        blocked_section, post = rest.split(MARKER_END, 1)
    else:
        blocked_section, post = rest, ""
    domains = []
    for line in blocked_section.strip().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "127.0.0.1":
                domains.append(parts[1])
    return pre, domains, post


def write_hosts(pre, domains, post):
    """Write updated /etc/hosts with blocked domains."""
    pre = pre.rstrip("\n")
    lines = [pre, "", MARKER_START]
    for d in sorted(set(domains)):
        lines.append(f"127.0.0.1   {d}")
    lines.append(MARKER_END)
    if post.strip():
        lines.append(post)
    lines.append("")
    with open(HOSTS_FILE, "w") as f:
        f.write("\n".join(lines))
    flush_dns()


def flush_dns():
    subprocess.run(["dscacheutil", "-flushcache"], capture_output=True)
    subprocess.run(["killall", "-HUP", "mDNSResponder"], capture_output=True)


def get_blocked_domains():
    _, domains, _ = read_hosts()
    return domains


def block_domain(domain):
    """Add a domain to /etc/hosts."""
    pre, domains, post = read_hosts()
    if domain not in domains:
        domains.append(domain)
        write_hosts(pre, domains, post)


def unblock_domain(domain):
    """Remove a domain from /etc/hosts."""
    pre, domains, post = read_hosts()
    if domain in domains:
        domains.remove(domain)
        write_hosts(pre, domains, post)


def add_permanent_domain(domain):
    domain = domain.strip().lower()
    if not domain or not re.match(r'^[a-z0-9]([a-z0-9\-]*\.)+[a-z]{2,}$', domain):
        return False, "Invalid domain"
    pre, domains, post = read_hosts()
    if domain in domains:
        return False, "Already blocked"
    # Don't add as permanent if it's a timed site
    timers = load_timers()
    for t in timers:
        if domain in t["domains"]:
            return False, "This domain is managed by a timer"
    domains.append(domain)
    write_hosts(pre, domains, post)
    return True, "Added"


# --- Timer management ---

def load_timers():
    """Load timers from JSON file."""
    if not os.path.exists(TIMERS_FILE):
        return []
    with open(TIMERS_FILE, "r") as f:
        return json.load(f)


def save_timers(timers):
    """Save timers to JSON file."""
    with open(TIMERS_FILE, "w") as f:
        json.dump(timers, f, indent=2)


def reset_if_new_day(timer):
    """Reset used_minutes if it's a new day."""
    today = date.today().isoformat()
    if timer.get("last_reset") != today:
        timer["used_minutes"] = 0
        timer["last_reset"] = today
        timer["active_session_end"] = None
        timer["session_start"] = None


def add_timer(name, domains, daily_minutes):
    """Add a new timed site group."""
    with timers_lock:
        timers = load_timers()
        # Check for duplicate domains
        existing = set()
        for t in timers:
            existing.update(t["domains"])
        for d in domains:
            if d in existing:
                return False, f"{d} already has a timer"
        timer = {
            "name": name,
            "domains": domains,
            "daily_minutes": daily_minutes,
            "used_minutes": 0,
            "last_reset": date.today().isoformat(),
            "active_session_end": None,
            "session_start": None,
        }
        timers.append(timer)
        save_timers(timers)
        # Ensure all timed domains are blocked initially
        for d in domains:
            block_domain(d)
        return True, "Timer added"


def start_session(timer_name, minutes):
    """Start a timed session — unblock domains for N minutes."""
    with timers_lock:
        timers = load_timers()
        for timer in timers:
            if timer["name"] == timer_name:
                reset_if_new_day(timer)
                remaining = timer["daily_minutes"] - timer["used_minutes"]
                if remaining <= 0:
                    return False, "Daily limit reached (0 min remaining)"
                if minutes > remaining:
                    minutes = remaining  # cap to remaining budget
                if timer["active_session_end"]:
                    return False, "Session already active"
                now = time.time()
                timer["active_session_end"] = now + (minutes * 60)
                timer["session_start"] = now
                save_timers(timers)
                # Unblock the domains
                for d in timer["domains"]:
                    unblock_domain(d)
                return True, f"Unblocked for {minutes} min"
        return False, "Timer not found"


def get_timers_status():
    """Get current status of all timers."""
    with timers_lock:
        timers = load_timers()
        result = []
        now = time.time()
        for timer in timers:
            reset_if_new_day(timer)
            remaining_budget = timer["daily_minutes"] - timer["used_minutes"]
            session_remaining = None
            if timer["active_session_end"]:
                session_remaining = max(0, int((timer["active_session_end"] - now) / 60))
            result.append({
                "name": timer["name"],
                "domains": timer["domains"],
                "daily_minutes": timer["daily_minutes"],
                "used_minutes": timer["used_minutes"],
                "remaining_minutes": max(0, remaining_budget),
                "session_active": timer["active_session_end"] is not None and timer["active_session_end"] > now,
                "session_remaining_minutes": session_remaining,
            })
        save_timers(timers)
        return result


def check_expired_sessions():
    """Background thread: re-block domains when sessions expire."""
    while True:
        time.sleep(15)
        with timers_lock:
            timers = load_timers()
            now = time.time()
            changed = False
            for timer in timers:
                reset_if_new_day(timer)
                if timer["active_session_end"] and now >= timer["active_session_end"]:
                    # Session expired — calculate used time
                    if timer["session_start"]:
                        used = (timer["active_session_end"] - timer["session_start"]) / 60
                        timer["used_minutes"] += used
                    timer["active_session_end"] = None
                    timer["session_start"] = None
                    changed = True
                    # Re-block the domains
                    for d in timer["domains"]:
                        block_domain(d)
            if changed:
                save_timers(timers)


# --- HTTP Handler ---

class BlockedHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/sites":
            self.send_json(200, {"domains": get_blocked_domains()})
        elif self.path == "/api/timers":
            self.send_json(200, {"timers": get_timers_status()})
        else:
            self.send_file("index.html", "text/html")

    def do_POST(self):
        if self.path == "/api/sites":
            body = self._read_body()
            if not body:
                return self.send_json(400, {"error": "No body"})
            domain = body.get("domain", "")
            ok, msg = add_permanent_domain(domain)
            self.send_json(200 if ok else 400, {"ok": ok, "message": msg})
        elif self.path == "/api/timers":
            body = self._read_body()
            if not body:
                return self.send_json(400, {"error": "No body"})
            name = body.get("name", "")
            domains = body.get("domains", [])
            daily_minutes = body.get("daily_minutes", 60)
            if not name or not domains:
                return self.send_json(400, {"ok": False, "message": "Name and domains required"})
            ok, msg = add_timer(name, domains, daily_minutes)
            self.send_json(200 if ok else 400, {"ok": ok, "message": msg})
        elif self.path == "/api/timers/start":
            body = self._read_body()
            if not body:
                return self.send_json(400, {"error": "No body"})
            name = body.get("name", "")
            minutes = body.get("minutes", 15)
            ok, msg = start_session(name, minutes)
            self.send_json(200 if ok else 400, {"ok": ok, "message": msg})
        else:
            self.send_json(404, {"error": "Not found"})

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(length))
        except Exception:
            return None

    def send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, filename, content_type):
        path = os.path.join(BLOCKED_DIR, filename)
        try:
            with open(path, "rb") as f:
                body = f.read()
            self.send_response(200)
        except FileNotFoundError:
            body = b"Not found"
            self.send_response(404)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def regenerate_server_cert():
    """Regenerate the server cert to include all currently blocked domains as SANs."""
    domains = get_blocked_domains()
    if not domains:
        return
    san_entries = ["DNS:" + d for d in domains] + ["IP:127.0.0.1"]
    san_str = ",".join(san_entries)

    # Generate server key
    subprocess.run([
        "openssl", "req", "-new", "-nodes",
        "-keyout", SERVER_KEY,
        "-out", os.path.join(CERTS_DIR, "server.csr"),
        "-subj", "/CN=Site Blocker",
    ], capture_output=True)

    # Write SAN extension file
    ext_file = os.path.join(CERTS_DIR, "san.ext")
    with open(ext_file, "w") as f:
        f.write(f"subjectAltName={san_str}\n")

    # Sign with CA
    subprocess.run([
        "openssl", "x509", "-req",
        "-in", os.path.join(CERTS_DIR, "server.csr"),
        "-CA", CA_CERT, "-CAkey", CA_KEY, "-CAcreateserial",
        "-out", SERVER_CERT,
        "-days", "825",
        "-extfile", ext_file,
    ], capture_output=True)


def ensure_certs():
    """Ensure CA and server certs exist."""
    os.makedirs(CERTS_DIR, exist_ok=True)
    if not os.path.exists(CA_KEY):
        # Generate CA
        subprocess.run([
            "openssl", "req", "-x509", "-new", "-nodes",
            "-keyout", CA_KEY, "-out", CA_CERT,
            "-days", "3650",
            "-subj", "/CN=Site Blocker CA",
        ], capture_output=True)
        # Trust the CA in macOS Keychain
        subprocess.run([
            "security", "add-trusted-cert", "-d",
            "-r", "trustRoot",
            "-k", "/Library/Keychains/System.keychain",
            CA_CERT,
        ], capture_output=True)
    regenerate_server_cert()


# Hook into add_permanent_domain to regenerate cert
_original_write_hosts = write_hosts
def write_hosts_and_regen_cert(pre, domains, post):
    _original_write_hosts(pre, domains, post)
    if os.path.exists(CA_KEY):
        regenerate_server_cert()
        # Reload HTTPS server's SSL context if possible
        global https_server
        if https_server:
            try:
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(SERVER_CERT, SERVER_KEY)
                https_server.socket = ctx.wrap_socket(https_server.socket, server_side=True)
            except Exception:
                pass
write_hosts = write_hosts_and_regen_cert

https_server = None


if __name__ == "__main__":
    # Start background thread for checking expired sessions
    watcher = threading.Thread(target=check_expired_sessions, daemon=True)
    watcher.start()

    # Ensure certs exist
    ensure_certs()

    # HTTP server on port 80
    http_server = http.server.HTTPServer(("127.0.0.1", 80), BlockedHandler)
    http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    http_thread.start()

    # HTTPS server on port 443
    https_server = http.server.HTTPServer(("127.0.0.1", 443), BlockedHandler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(SERVER_CERT, SERVER_KEY)
    https_server.socket = ctx.wrap_socket(https_server.socket, server_side=True)
    https_server.serve_forever()
