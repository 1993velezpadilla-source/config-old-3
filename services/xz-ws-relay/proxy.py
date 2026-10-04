#!/usr/bin/env python3
import asyncio
import os
import signal
import subprocess
import time

PUBLIC_PORT = int(os.environ.get("PORT", "10000"))
INTERNAL_PORT = int(os.environ.get("XZ_RELAY_INTERNAL_PORT", "10001"))
READY_DELAY = float(os.environ.get("XZ_RELAY_READY_DELAY", "8"))
GODOT_BIN = os.environ.get("XZ_GODOT_BIN", ".render/godot/Godot_v4.6.1-stable_linux.x86_64")
STARTED_AT = time.monotonic()
_child = None

def relay_ready():
    return _child is not None and _child.poll() is None and (time.monotonic() - STARTED_AT) >= READY_DELAY

def http_response(status, payload):
    body = payload.encode("utf-8")
    reason = "OK" if status == 200 else "Service Unavailable"
    return (
        f"HTTP/1.1 {status} {reason}\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Cache-Control: no-store\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("ascii") + body

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

async def handle_client(reader, writer):
    try:
        request = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5.0)
    except Exception:
        writer.close()
        await writer.wait_closed()
        return

    lower = request.lower()
    is_websocket = b"upgrade: websocket" in lower and b"connection:" in lower

    if not is_websocket:
        status = 200 if relay_ready() else 503
        payload = (
            '{"ok":true,"service":"xz-zombie-relay","ready":true}'
            if status == 200
            else '{"ok":false,"service":"xz-zombie-relay","ready":false}'
        )
        writer.write(http_response(status, payload))
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        return

    if not relay_ready():
        writer.write(http_response(503, '{"ok":false,"error":"relay_starting"}'))
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        return

    try:
        upstream_reader, upstream_writer = await asyncio.open_connection("127.0.0.1", INTERNAL_PORT)
    except OSError:
        writer.write(http_response(503, '{"ok":false,"error":"relay_unavailable"}'))
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        return

    upstream_writer.write(request)
    await upstream_writer.drain()
    a = asyncio.create_task(pipe(reader, upstream_writer))
    b = asyncio.create_task(pipe(upstream_reader, writer))
    _, pending = await asyncio.wait({a, b}, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)

def start_godot():
    global _child
    env = os.environ.copy()
    env["PORT"] = str(INTERNAL_PORT)
    cmd = [
        GODOT_BIN,
        "--headless",
        "--path",
        "xogot",
        "--script",
        "res://server/public_ws_dedicated.gd",
    ]
    print("XZ_RELAY_GATEWAY_SPAWN", " ".join(cmd), "internal_port=", INTERNAL_PORT, flush=True)
    _child = subprocess.Popen(cmd, env=env)

async def main():
    start_godot()
    server = await asyncio.start_server(handle_client, "0.0.0.0", PUBLIC_PORT)
    print(f"XZ_RELAY_GATEWAY_READY 0.0.0.0:{PUBLIC_PORT} -> 127.0.0.1:{INTERNAL_PORT}", flush=True)
    async with server:
        await server.serve_forever()

def shutdown(*_args):
    if _child is not None and _child.poll() is None:
        _child.terminate()
        try:
            _child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _child.kill()
    raise SystemExit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    try:
        asyncio.run(main())
    finally:
        if _child is not None and _child.poll() is None:
            _child.terminate()
