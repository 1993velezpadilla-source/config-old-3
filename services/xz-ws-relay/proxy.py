#!/usr/bin/env python3
import asyncio
import json
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit

PUBLIC_PORT = int(os.environ.get("PORT", "10000"))
BASE_INTERNAL_PORT = int(os.environ.get("XZ_RELAY_INTERNAL_PORT", "10001"))
MAX_ROOMS = max(1, int(os.environ.get("XZ_RELAY_MAX_ROOMS", "2")))
MIN_WARM_ROOMS = min(MAX_ROOMS, max(1, int(os.environ.get("XZ_RELAY_MIN_WARM_ROOMS", str(MAX_ROOMS)))))
ROOM_CAPACITY = 4
RPC_SCENE_ROOT = "YouWontWin"
RUNTIME_CONTRACT = "multiroom-mobile-voice-v7"
READY_DELAY = max(0.1, float(os.environ.get("XZ_RELAY_READY_DELAY", "8")))
READY_TIMEOUT_SECONDS = max(15.0, float(os.environ.get("XZ_RELAY_READY_TIMEOUT_SECONDS", "35")))
ROOM_IDLE_SECONDS = max(10.0, float(os.environ.get("XZ_RELAY_ROOM_IDLE_SECONDS", "90")))
RECONNECT_GRACE_SECONDS = max(10.0, float(os.environ.get("XZ_RELAY_RECONNECT_GRACE_SECONDS", "45")))
GODOT_BIN = os.environ.get("XZ_GODOT_BIN", ".render/godot/Godot_v4.6.1-stable_linux.x86_64")

@dataclass
class Room:
    room_id: str
    port: int
    child: subprocess.Popen
    started_at: float
    connections: int = 0
    last_used: float = 0.0
    ready: bool = False

@dataclass
class ResumeRoute:
    room_id: str
    active: bool = True
    expires_at: float = 0.0

_rooms = {}
_resume_routes = {}
_room_counter = 0
_room_lock = None

def room_alive(room):
    return room is not None and room.child.poll() is None

def room_ready(room):
    return room_alive(room) and room.ready

def pump_room_output(room):
    stream = room.child.stdout
    if stream is None:
        return
    marker = f"XZOGOT_PUBLIC_RELAY_HEADLESS_SCENE_GREEN room={room.room_id}"
    try:
        for raw_line in stream:
            line = raw_line.rstrip("\r\n")
            if line:
                print(line, flush=True)
            if marker in line and not room.ready:
                room.ready = True
                print(
                    f"XZ_RELAY_ROOM_READY id={room.room_id} port={room.port}",
                    flush=True,
                )
    except Exception as exc:
        print(
            f"XZ_RELAY_ROOM_LOG_PUMP_ERROR id={room.room_id} error={exc}",
            flush=True,
        )

def valid_resume_token(token):
    if not token or len(token) < 16 or len(token) > 96:
        return False
    return all(ch.isalnum() or ch in "_-" for ch in token)

def cleanup_resume_routes_locked(now=None):
    now = time.monotonic() if now is None else now
    expired = [
        token
        for token, route in _resume_routes.items()
        if not route.active and route.expires_at <= now
    ]
    for token in expired:
        route = _resume_routes.pop(token, None)
        if route is not None:
            print(f"XZ_RELAY_RESUME_EXPIRED room={route.room_id}", flush=True)

def reserved_count(room_id):
    now = time.monotonic()
    return sum(
        1
        for route in _resume_routes.values()
        if route.room_id == room_id
        and not route.active
        and route.expires_at > now
    )

def room_effective_load(room):
    return room.connections + reserved_count(room.room_id)

def http_response(status, payload, include_body=True):
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    reasons = {
        200: "OK",
        404: "Not Found",
        429: "Too Many Requests",
        503: "Service Unavailable",
    }
    reason = reasons.get(status, "Error")
    headers = (
        f"HTTP/1.1 {status} {reason}\r\n"
        "Content-Type: application/json; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Cache-Control: no-store\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("ascii")
    return headers + (body if include_body else b"")

def start_room():
    global _room_counter
    _room_counter += 1
    room_id = f"r{_room_counter}"
    port = BASE_INTERNAL_PORT + _room_counter - 1
    if port > 65535:
        raise RuntimeError("relay internal port range exhausted")
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["XZ_RELAY_ROOM_ID"] = room_id
    env["XZOGOT_DEDICATED"] = "1"
    cmd = [
        GODOT_BIN,
        "--headless",
        "--path",
        "xogot",
        "--script",
        "res://server/public_ws_dedicated.gd",
    ]
    child = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    stamp = time.monotonic()
    room = Room(
        room_id=room_id,
        port=port,
        child=child,
        started_at=stamp,
        last_used=stamp,
    )
    _rooms[room_id] = room
    threading.Thread(
        target=pump_room_output,
        args=(room,),
        name=f"xz-room-log-{room_id}",
        daemon=True,
    ).start()
    print(
        f"XZ_RELAY_ROOM_SPAWN id={room_id} port={port} pid={child.pid} "
        f"capacity={ROOM_CAPACITY} warm_rooms={MIN_WARM_ROOMS}",
        flush=True,
    )
    return room

def stop_room(room, reason):
    if room is None:
        return
    _rooms.pop(room.room_id, None)
    for token in [
        value
        for value, route in _resume_routes.items()
        if route.room_id == room.room_id
    ]:
        _resume_routes.pop(token, None)
    if room.child.poll() is None:
        room.child.terminate()
        try:
            room.child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            room.child.kill()
            room.child.wait(timeout=2)
    print(
        f"XZ_RELAY_ROOM_STOP id={room.room_id} reason={reason} "
        f"connections={room.connections}",
        flush=True,
    )

def room_snapshot():
    payload = []
    for room in sorted(_rooms.values(), key=lambda value: value.room_id):
        reserved = reserved_count(room.room_id)
        payload.append({
            "id": room.room_id,
            "players": room.connections,
            "reserved": reserved,
            "effective_load": room.connections + reserved,
            "capacity": ROOM_CAPACITY,
            "ready": room_ready(room),
        })
    return payload

async def allocate_room(requested_room="", resume_token=""):
    async with _room_lock:
        cleanup_resume_routes_locked()
        dead = [room for room in _rooms.values() if not room_alive(room)]
        for room in dead:
            stop_room(room, "child_exit")

        if valid_resume_token(resume_token) and resume_token in _resume_routes:
            route = _resume_routes[resume_token]
            candidate = _rooms.get(route.room_id)
            if candidate is not None and room_alive(candidate):
                if route.active:
                    return None
                candidate.connections += 1
                candidate.last_used = time.monotonic()
                route.active = True
                route.expires_at = 0.0
                print(
                    f"XZ_RELAY_RESUME_ROUTE room={candidate.room_id} "
                    f"occupancy={candidate.connections}/{ROOM_CAPACITY}",
                    flush=True,
                )
                return candidate
            _resume_routes.pop(resume_token, None)

        room = None
        if requested_room:
            candidate = _rooms.get(requested_room)
            if candidate is not None and room_effective_load(candidate) < ROOM_CAPACITY:
                room = candidate
        else:
            for candidate in sorted(_rooms.values(), key=lambda value: value.room_id):
                if room_effective_load(candidate) < ROOM_CAPACITY:
                    room = candidate
                    break
            if room is None and len(_rooms) < MAX_ROOMS:
                room = start_room()

        if room is None:
            return None

        room.connections += 1
        room.last_used = time.monotonic()
        if valid_resume_token(resume_token):
            _resume_routes[resume_token] = ResumeRoute(
                room_id=room.room_id,
                active=True,
                expires_at=0.0,
            )
        print(
            f"XZ_RELAY_ASSIGN room={room.room_id} "
            f"occupancy={room.connections}/{ROOM_CAPACITY} "
            f"reserved={reserved_count(room.room_id)}",
            flush=True,
        )
        return room

async def release_room(room, resume_token=""):
    async with _room_lock:
        if room.room_id not in _rooms:
            return
        room.connections = max(0, room.connections - 1)
        room.last_used = time.monotonic()
        if valid_resume_token(resume_token):
            route = _resume_routes.get(resume_token)
            if route is not None and route.room_id == room.room_id:
                route.active = False
                route.expires_at = time.monotonic() + RECONNECT_GRACE_SECONDS
                print(
                    f"XZ_RELAY_RESUME_RESERVED room={room.room_id} "
                    f"grace={RECONNECT_GRACE_SECONDS:.0f}s",
                    flush=True,
                )
        print(
            f"XZ_RELAY_RELEASE room={room.room_id} "
            f"occupancy={room.connections}/{ROOM_CAPACITY} "
            f"reserved={reserved_count(room.room_id)}",
            flush=True,
        )

async def wait_room_ready(room):
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if not room_alive(room):
            return False
        if room_ready(room):
            return True
        await asyncio.sleep(0.1)
    return False

async def pipe(reader, writer):
    try:
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

def request_parts(request):
    first_line = request.split(b"\r\n", 1)[0].decode("latin-1", errors="ignore")
    pieces = first_line.split(" ")
    method = pieces[0].upper() if pieces else "GET"
    target = pieces[1] if len(pieces) > 1 else "/"
    split = urlsplit(target)
    return method, split.path, split.query

def resume_token_from_query(query):
    values = parse_qs(query, keep_blank_values=False).get("resume", [])
    token = values[0].strip() if values else ""
    return token if valid_resume_token(token) else ""

def upstream_request_without_resume(request):
    first, separator, rest = request.partition(b"\r\n")
    if not separator:
        return request
    try:
        line = first.decode("latin-1")
        pieces = line.split(" ")
        if len(pieces) < 3:
            return request
        split = urlsplit(pieces[1])
        filtered = [
            (key, value)
            for key, value in parse_qsl(split.query, keep_blank_values=True)
            if key != "resume"
        ]
        clean_target = split.path or "/"
        clean_query = urlencode(filtered, doseq=True)
        if clean_query:
            clean_target += "?" + clean_query
        pieces[1] = clean_target
        return " ".join(pieces).encode("latin-1") + separator + rest
    except Exception:
        return request

def requested_room_from_path(path):
    prefix = "/room/"
    if not path.startswith(prefix):
        return ""
    room_id = path[len(prefix):].strip().split("/", 1)[0]
    return room_id[:32]

async def handle_http(method, path, writer):
    include_body = method != "HEAD"
    if path in ("/", "/health"):
        rooms = room_snapshot()
        ready = any(room["ready"] for room in rooms)
        status = 200 if ready else 503
        writer.write(http_response(status, {
            "ok": ready,
            "service": "xz-zombie-relay",
            "ready": ready,
            "multi_room": True,
            "rpc_scene_root": RPC_SCENE_ROOT,
            "runtime_contract": RUNTIME_CONTRACT,
            "reconnect_grace_seconds": RECONNECT_GRACE_SECONDS,
            "room_ready_contract": "godot-marker-v1",
            "room_ready_timeout_seconds": READY_TIMEOUT_SECONDS,
            "room_capacity": ROOM_CAPACITY,
            "max_rooms": MAX_ROOMS,
            "min_warm_rooms": MIN_WARM_ROOMS,
            "active_rooms": len(rooms),
        }, include_body))
    elif path == "/v1/rooms":
        rooms = room_snapshot()
        writer.write(http_response(200, {
            "rooms": rooms,
            "room_capacity": ROOM_CAPACITY,
            "max_rooms": MAX_ROOMS,
            "min_warm_rooms": MIN_WARM_ROOMS,
            "reconnect_grace_seconds": RECONNECT_GRACE_SECONDS,
        }, include_body))
    else:
        writer.write(http_response(404, {"error": "not_found"}, include_body))
    await writer.drain()
    writer.close()
    await writer.wait_closed()

async def handle_client(reader, writer):
    try:
        request = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5.0)
    except Exception:
        writer.close()
        await writer.wait_closed()
        return

    method, path, query = request_parts(request)
    resume_token = resume_token_from_query(query)
    lower = request.lower()
    is_websocket = b"upgrade: websocket" in lower and b"connection:" in lower

    if not is_websocket:
        await handle_http(method, path, writer)
        return

    if path not in ("/", "/matchmake") and not path.startswith("/room/"):
        writer.write(http_response(404, {"error": "websocket_path_not_found"}))
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        return

    requested_room = requested_room_from_path(path)
    room = await allocate_room(requested_room, resume_token)
    if room is None:
        status = 404 if requested_room else 429
        error = "room_not_found_or_full" if requested_room else "all_rooms_full"
        writer.write(http_response(status, {"ok": False, "error": error}))
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        return

    try:
        if not await wait_room_ready(room):
            writer.write(http_response(503, {"ok": False, "error": "room_start_failed"}))
            await writer.drain()
            return

        try:
            upstream_reader, upstream_writer = await asyncio.open_connection("127.0.0.1", room.port)
        except OSError:
            writer.write(http_response(503, {"ok": False, "error": "room_unavailable"}))
            await writer.drain()
            return

        upstream_request = upstream_request_without_resume(request)
        if resume_token:
            print(
                f"XZ_RELAY_RESUME_QUERY_STRIPPED room={room.room_id}",
                flush=True,
            )
        upstream_writer.write(upstream_request)
        await upstream_writer.drain()
        downstream = asyncio.create_task(pipe(reader, upstream_writer))
        upstream = asyncio.create_task(pipe(upstream_reader, writer))
        _, pending = await asyncio.wait(
            {downstream, upstream},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
    finally:
        await release_room(room, resume_token)
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

async def reap_idle_rooms():
    while True:
        await asyncio.sleep(5.0)
        async with _room_lock:
            cleanup_resume_routes_locked()
            if len(_rooms) <= MIN_WARM_ROOMS:
                continue
            now = time.monotonic()
            candidates = [
                room
                for room in sorted(_rooms.values(), key=lambda value: value.room_id, reverse=True)
                if room.connections == 0 and now - room.last_used >= ROOM_IDLE_SECONDS
            ]
            for room in candidates:
                if len(_rooms) <= MIN_WARM_ROOMS:
                    break
                stop_room(room, "idle")

async def main():
    global _room_lock
    _room_lock = asyncio.Lock()
    for _index in range(MIN_WARM_ROOMS):
        start_room()
    print(
        f"XZ_RELAY_WARM_POOL_STARTED rooms={MIN_WARM_ROOMS}/{MAX_ROOMS}",
        flush=True,
    )
    reaper = asyncio.create_task(reap_idle_rooms())
    server = await asyncio.start_server(handle_client, "0.0.0.0", PUBLIC_PORT)
    print(
        f"XZ_RELAY_GATEWAY_READY 0.0.0.0:{PUBLIC_PORT} "
        f"base_internal_port={BASE_INTERNAL_PORT} max_rooms={MAX_ROOMS} "
        f"capacity={ROOM_CAPACITY}",
        flush=True,
    )
    try:
        async with server:
            await server.serve_forever()
    finally:
        reaper.cancel()
        await asyncio.gather(reaper, return_exceptions=True)

def shutdown_children():
    for room in list(_rooms.values()):
        stop_room(room, "shutdown")

def shutdown(*_args):
    shutdown_children()
    raise SystemExit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    try:
        asyncio.run(main())
    finally:
        shutdown_children()
