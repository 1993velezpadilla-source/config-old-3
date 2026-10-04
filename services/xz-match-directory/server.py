#!/usr/bin/env python3
import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))
TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "25"))
TRUST_SUPPLIED_IP = os.environ.get("XZ_MATCH_TRUST_SUPPLIED_IP", "").strip().lower() in {
    "1", "true", "yes", "on"
}
MAX_BODY = 16 * 1024

_lock = threading.Lock()
_sessions = {}

def now():
    return time.time()

def prune():
    cutoff = now()
    stale = [sid for sid, s in _sessions.items() if float(s["expires_at"]) <= cutoff]
    for sid in stale:
        _sessions.pop(sid, None)

def clean_text(value, default, max_len):
    text = str(value or "").strip()
    if not text:
        text = default
    return text[:max_len]

class Handler(BaseHTTPRequestHandler):
    server_version = "XZMatchDirectory/1.0"

    def log_message(self, fmt, *args):
        print("XZDIR", self.address_string(), fmt % args, flush=True)

    def _headers(self, status=200, content_length=None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-XZ-Host-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        if content_length is not None:
            self.send_header("Content-Length", str(int(content_length)))
        self.end_headers()

    def _json(self, status, payload):
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self._headers(status, len(encoded))
        self.wfile.write(encoded)
        self.wfile.flush()

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length <= 0 or length > MAX_BODY:
            return None
        raw = self.rfile.read(length)
        try:
            value = json.loads(raw.decode("utf-8"))
        except Exception:
            return None
        return value if isinstance(value, dict) else None

    def _client_ip(self):
        forwarded = self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        return forwarded or self.client_address[0]

    def do_OPTIONS(self):
        self._headers(204, 0)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json(200, {"ok": True, "service": "xz-match-directory", "version": 1})
            return
        if parsed.path != "/v1/sessions":
            self._json(404, {"error": "not_found"})
            return
        with _lock:
            prune()
            public = []
            for s in _sessions.values():
                if int(s["players"]) >= int(s["max_players"]):
                    continue
                public.append({
                    "id": s["id"],
                    "name": s["name"],
                    "map": s["map"],
                    "ip": s["ip"],
                    "port": s["port"],
                    "players": s["players"],
                    "max_players": s["max_players"],
                    "protocol": s["protocol"],
                    "updated_at": s["updated_at"],
                })
            public.sort(key=lambda s: (-int(s["players"]), -float(s["updated_at"])))
        self._json(200, {"sessions": public, "ttl_seconds": TTL_SECONDS})

    def do_POST(self):
        if urlparse(self.path).path != "/v1/sessions/register":
            self._json(404, {"error": "not_found"})
            return
        body = self._body()
        if body is None:
            self._json(400, {"error": "invalid_json"})
            return
        try:
            port = int(body.get("port", 0))
            players = int(body.get("players", 1))
            max_players = int(body.get("max_players", 4))
            protocol = int(body.get("protocol", 1))
        except Exception:
            self._json(400, {"error": "invalid_numbers"})
            return
        if not (1024 <= port <= 65535 and 1 <= players <= max_players == 4 and protocol == 1):
            self._json(400, {"error": "invalid_session"})
            return

        session_id = clean_text(body.get("id"), "", 96)
        host_token = clean_text(body.get("host_token"), "", 128)
        if not session_id:
            session_id = secrets.token_hex(12)
        if not host_token:
            host_token = secrets.token_hex(24)

        supplied_ip = clean_text(body.get("ip"), "", 64)
        observed_ip = self._client_ip()
        ip = supplied_ip if TRUST_SUPPLIED_IP and supplied_ip else observed_ip
        timestamp = now()
        with _lock:
            prune()
            old = _sessions.get(session_id)
            if old is not None and old["host_token"] != host_token:
                self._json(409, {"error": "session_owned"})
                return
            _sessions[session_id] = {
                "id": session_id,
                "host_token": host_token,
                "name": clean_text(body.get("name"), "YOU WON'T WIN", 64),
                "map": clean_text(body.get("map"), "CHURCH", 64),
                "ip": ip,
                "port": port,
                "players": players,
                "max_players": max_players,
                "protocol": protocol,
                "updated_at": timestamp,
                "expires_at": timestamp + TTL_SECONDS,
            }
        self._json(200, {
            "ok": True,
            "id": session_id,
            "host_token": host_token,
            "expires_in": TTL_SECONDS,
        })

    def do_DELETE(self):
        parsed = urlparse(self.path)
        prefix = "/v1/sessions/"
        if not parsed.path.startswith(prefix):
            self._json(404, {"error": "not_found"})
            return
        session_id = parsed.path[len(prefix):].strip()
        host_token = self.headers.get("X-XZ-Host-Token", "").strip()
        with _lock:
            prune()
            old = _sessions.get(session_id)
            if old is None:
                self._json(200, {"ok": True, "deleted": False})
                return
            if not host_token or old["host_token"] != host_token:
                self._json(403, {"error": "forbidden"})
                return
            _sessions.pop(session_id, None)
        self._json(200, {"ok": True, "deleted": True})

if __name__ == "__main__":
    print(
        f"XZ_MATCH_DIRECTORY_READY {HOST}:{PORT} ttl={TTL_SECONDS} "
        f"trust_supplied_ip={TRUST_SUPPLIED_IP}",
        flush=True,
    )
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
