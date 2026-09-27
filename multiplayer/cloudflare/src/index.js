import { DurableObject } from "cloudflare:workers";

const MAX_PLAYERS = 4;
const CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
const GAME_MAGIC = [0x58, 0x5a, 0x44, 0x31]; // XZD1
const GAME_HEADER_BYTES = 9;
// Vril chunks reliable traffic into NET_DATAGRAMSIZE <= 8008 bytes.
// Keep the tunnel ceiling above that so signon/precache packets survive.
const MAX_GAME_DATAGRAM = 8192;
const MAX_VOICE_PACKET = 4096;
const DEFAULT_MAP = "ndu";

function roomCode() {
  const b = new Uint8Array(6);
  crypto.getRandomValues(b);
  let out = "";
  for (const n of b) out += CODE_CHARS[n % CODE_CHARS.length];
  return out;
}

function sanitizeMap(value) {
  // v0.26 ships Nacht as the online test map. Keep this centralized so
  // additional bundled maps can be allow-listed without touching clients.
  return String(value || DEFAULT_MAP).toLowerCase() === "ndu" ? "ndu" : DEFAULT_MAP;
}

function sanitizeTargetPlayers(value) {
  const n = Number(value);
  return n === 2 || n === 3 || n === 4 ? n : MAX_PLAYERS;
}

function sanitizeHostPriority(value) {
  return Number(value) > 0 ? 1 : 0;
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store",
    },
  });
}

function upgrade(request) {
  return request.headers.get("Upgrade")?.toLowerCase() === "websocket";
}

function isGamePacket(bytes) {
  return bytes.length >= GAME_HEADER_BYTES &&
    bytes[0] === GAME_MAGIC[0] &&
    bytes[1] === GAME_MAGIC[1] &&
    bytes[2] === GAME_MAGIC[2] &&
    bytes[3] === GAME_MAGIC[3];
}

function isVoicePacket(bytes) {
  return bytes.length > 24 &&
    bytes[0] === 0x58 && // X
    bytes[1] === 0x56 && // V
    bytes[2] === 0x43 && // C
    bytes[3] === 0x31;   // 1
}

async function initRoom(env, code, options = {}) {
  const id = env.GAME_ROOMS.idFromName(code);
  const stub = env.GAME_ROOMS.get(id);
  await stub.fetch(new Request("https://room/init", {
    method: "POST",
    body: JSON.stringify({
      code,
      map: sanitizeMap(options.map),
      mode: options.mode === "public" ? "public" : "private",
      targetPlayers: sanitizeTargetPlayers(options.targetPlayers),
      reservations: options.reservations || {},
      worldPhase: "lobby",
      worldRevision: 0,
    }),
  }));
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return json({
        ok: true,
        service: "xziel-multiplayer",
        transport: "websocket-datagram-tunnel",
        maxPlayers: MAX_PLAYERS,
        matchmaking: true,
      });
    }

    if (request.method === "POST" && url.pathname === "/api/rooms/create") {
      let body = {};
      try { body = await request.json(); } catch {}

      const code = roomCode();
      const ownerPlayerId = String(body.playerId || "").slice(0, 64);
      const reservations = ownerPlayerId ? { [ownerPlayerId]: 1 } : {};
      const map = sanitizeMap(body.map);

      await initRoom(env, code, {
        map,
        mode: "private",
        reservations,
      });

      return json({
        roomCode: code,
        map,
        mode: "private",
        maxPlayers: MAX_PLAYERS,
      });
    }

    if (url.pathname === "/matchmake" && upgrade(request)) {
      const rawQueue = String(url.searchParams.get("queue") || "public-v1");
      const queue = rawQueue.replace(/[^A-Za-z0-9_-]/g, "").slice(0, 64) || "public-v1";
      const map = sanitizeMap(url.searchParams.get("map"));
      const targetPlayers = sanitizeTargetPlayers(url.searchParams.get("players"));
      const hostPriority = sanitizeHostPriority(url.searchParams.get("hostPriority"));
      const id = env.MATCHMAKER.idFromName(
        "queue-" + queue + "-" + map + "-" + targetPlayers
      );
      const stub = env.MATCHMAKER.get(id);
      const target = new URL(request.url);
      target.pathname = "/socket";
      target.searchParams.set("queue", queue);
      target.searchParams.set("map", map);
      target.searchParams.set("players", String(targetPlayers));
      target.searchParams.set("hostPriority", String(hostPriority));
      return stub.fetch(new Request(target, request));
    }

    const match = url.pathname.match(/^\/(game|voice)\/([A-Z0-9]{6})$/);
    if (match && upgrade(request)) {
      const [, kind, code] = match;
      const id = env.GAME_ROOMS.idFromName(code);
      const stub = env.GAME_ROOMS.get(id);
      const target = new URL(request.url);
      target.pathname = "/socket";
      target.searchParams.set("kind", kind);
      target.searchParams.set("room", code);
      return stub.fetch(new Request(target, request));
    }

    return json({ error: "not_found" }, 404);
  },
};

export class Matchmaker extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.ctx = ctx;
    this.env = env;
  }

  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname !== "/socket" || !upgrade(request)) {
      return json({ error: "upgrade_required" }, 426);
    }

    const playerId = String(
      url.searchParams.get("playerId") || crypto.randomUUID()
    ).slice(0, 64);
    const map = sanitizeMap(url.searchParams.get("map"));
    const targetPlayers = sanitizeTargetPlayers(url.searchParams.get("players"));
    const hostPriority = sanitizeHostPriority(
      url.searchParams.get("hostPriority")
    );

    // One active queue socket per player ID.
    for (const socket of this.ctx.getWebSockets()) {
      const a = socket.deserializeAttachment() || {};
      if (a.playerId === playerId) {
        try { socket.close(1000, "replaced"); } catch {}
      }
    }

    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);
    this.ctx.acceptWebSocket(server);
    server.serializeAttachment({
      playerId,
      map,
      targetPlayers,
      hostPriority,
      joinedAt: Date.now(),
    });

    try {
      server.send(JSON.stringify({
        type: "searching",
        map,
        targetPlayers,
        needed: targetPlayers,
        queued: this.queueForCriteria(map, targetPlayers).length,
      }));
    } catch {}

    await this.tryCreateMatch(map, targetPlayers);
    this.broadcastQueueStatus(map, targetPlayers);
    return new Response(null, { status: 101, webSocket: client });
  }

  queueForCriteria(map, targetPlayers) {
    const out = [];
    for (const socket of this.ctx.getWebSockets()) {
      const a = socket.deserializeAttachment() || {};
      if (a.map === map &&
          a.targetPlayers === targetPlayers &&
          a.playerId) {
        out.push({ socket, ...a });
      }
    }
    out.sort((a, b) => {
      const priority = Number(b.hostPriority || 0) - Number(a.hostPriority || 0);
      if (priority !== 0) return priority;
      return a.joinedAt - b.joinedAt;
    });
    return out;
  }

  async tryCreateMatch(map, targetPlayers) {
    const queue = this.queueForCriteria(map, targetPlayers);
    if (queue.length < targetPlayers) return;

    const group = queue.slice(0, targetPlayers);
    const code = roomCode();
    const reservations = {};
    group.forEach((entry, index) => {
      reservations[entry.playerId] = index + 1;
    });

    await initRoom(this.env, code, {
      map,
      mode: "public",
      targetPlayers,
      reservations,
    });

    for (const entry of group) {
      try {
        entry.socket.send(JSON.stringify({
          type: "match_found",
          roomCode: code,
          map,
          mode: "public",
          targetPlayers,
          maxPlayers: targetPlayers,
        }));
        entry.socket.close(1000, "matched");
      } catch {}
    }
  }

  webSocketMessage() {}

  webSocketClose(ws) {
    const a = ws.deserializeAttachment() || {};
    if (a.map) this.broadcastQueueStatus(
      a.map,
      sanitizeTargetPlayers(a.targetPlayers)
    );
  }

  webSocketError() {}

  broadcastQueueStatus(map, targetPlayers) {
    const queue = this.queueForCriteria(map, targetPlayers);
    for (const entry of queue) {
      try {
        entry.socket.send(JSON.stringify({
          type: "searching",
          map,
          targetPlayers,
          queued: queue.length,
          needed: targetPlayers,
        }));
      } catch {}
    }
  }
}

export class GameRoom extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.ctx = ctx;
  }

  async fetch(request) {
    const url = new URL(request.url);

    if (request.method === "POST" && url.pathname === "/init") {
      const body = await request.json();
      await this.ctx.storage.put({
        roomCode: String(body.code || ""),
        map: sanitizeMap(body.map),
        mode: body.mode === "public" ? "public" : "private",
        targetPlayers: sanitizeTargetPlayers(body.targetPlayers),
        reservations: body.reservations || {},
        worldPhase: "lobby",
        worldRevision: 0,
      });
      return json({ ok: true });
    }

    if (url.pathname !== "/socket" || !upgrade(request)) {
      return json({ error: "upgrade_required" }, 426);
    }

    const state = await this.ctx.storage.get([
      "roomCode", "map", "mode", "targetPlayers", "reservations",
      "worldPhase", "worldRevision",
    ]);
    const expectedRoom = String(state.get("roomCode") || "");
    const requestedRoom = String(url.searchParams.get("room") || "");
    if (!expectedRoom || requestedRoom !== expectedRoom) {
      return json({ error: "room_not_found" }, 404);
    }

    const roomMap = sanitizeMap(state.get("map"));
    const roomMode = state.get("mode") === "public" ? "public" : "private";
    const roomMaxPlayers = roomMode === "public"
      ? sanitizeTargetPlayers(state.get("targetPlayers"))
      : MAX_PLAYERS;
    const reservations = state.get("reservations") || {};
    const storedWorldPhase = state.get("worldPhase");
    const worldPhase = ["lobby", "preparing", "live"].includes(storedWorldPhase)
      ? storedWorldPhase : "lobby";
    const storedWorldRevision = state.get("worldRevision");
    const worldRevision = Number.isFinite(Number(storedWorldRevision))
      ? Number(storedWorldRevision) : 0;
    const kind = url.searchParams.get("kind") === "voice" ? "voice" : "game";
    const playerId = String(
      url.searchParams.get("playerId") || crypto.randomUUID()
    ).slice(0, 64);
    const sockets = this.ctx.getWebSockets();

    const gameByPlayer = new Map();
    const usedSlots = new Set();
    for (const socket of sockets) {
      const a = socket.deserializeAttachment() || {};
      if (a.kind === "game") {
        gameByPlayer.set(a.playerId, a);
        usedSlots.add(a.slot);
      }
    }

    let slot = 0;
    if (kind === "game") {
      const existing = gameByPlayer.get(playerId);
      if (existing) {
        slot = existing.slot;
      } else {
        if (gameByPlayer.size >= roomMaxPlayers) {
          return json({ error: "room_full", maxPlayers: roomMaxPlayers }, 409);
        }

        const reserved = Number(reservations[playerId] || 0);
        if (reserved >= 1 && reserved <= roomMaxPlayers && !usedSlots.has(reserved)) {
          slot = reserved;
        } else {
          for (let candidate = 1; candidate <= roomMaxPlayers; candidate += 1) {
            if (!usedSlots.has(candidate) &&
                !Object.values(reservations).includes(candidate)) {
              slot = candidate;
              break;
            }
          }
          if (!slot) {
            for (let candidate = 1; candidate <= roomMaxPlayers; candidate += 1) {
              if (!usedSlots.has(candidate)) {
                slot = candidate;
                break;
              }
            }
          }
        }
      }
    } else {
      const game = gameByPlayer.get(playerId);
      if (!game) {
        return json({ error: "join_game_socket_first" }, 403);
      }
      slot = game.slot;
    }

    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);
    this.ctx.acceptWebSocket(server);
    server.serializeAttachment({
      kind,
      playerId,
      slot,
      map: roomMap,
      mode: roomMode,
      targetPlayers: roomMaxPlayers,
    });

    if (kind === "game") {
      const playerSlots = Array.from(gameByPlayer.values())
        .map(a => a.slot)
        .filter(value => value >= 1 && value <= roomMaxPlayers);
      if (!playerSlots.includes(slot)) playerSlots.push(slot);
      playerSlots.sort((a, b) => a - b);

      try {
        server.send(JSON.stringify({
          type: "welcome",
          roomCode: expectedRoom,
          playerId,
          slot,
          players: playerSlots,
          map: roomMap,
          mode: roomMode,
          targetPlayers: roomMaxPlayers,
          maxPlayers: roomMaxPlayers,
          hostSlot: 1,
          worldPhase,
          worldRevision,
          serverTime: Date.now(),
        }));
      } catch {}

      this.broadcastJson(
        {
          type: "player_joined",
          playerId,
          slot,
          map: roomMap,
          mode: roomMode,
          targetPlayers: roomMaxPlayers,
          worldPhase,
          worldRevision,
        },
        server,
      );

      // A reconnecting client must rejoin the exact authoritative world that
      // already exists on Player 1. Never ask it to create/load its own map.
      if (slot !== 1 && worldPhase === "preparing") {
        try {
          server.send(JSON.stringify({
            type: "prepare_game",
            map: roomMap,
            worldPhase,
            worldRevision,
            replay: true,
            serverTime: Date.now(),
          }));
        } catch {}
      } else if (slot !== 1 && worldPhase === "live") {
        try {
          server.send(JSON.stringify({
            type: "server_ready",
            map: roomMap,
            worldPhase,
            worldRevision,
            replay: true,
            serverTime: Date.now(),
          }));
        } catch {}
      }

      // Public rooms auto-start when their selected Duo/Trio/Quad size is full.
      // Private rooms remain host-controlled.
      if (roomMode === "public") {
        let count = 0;
        for (const socket of this.ctx.getWebSockets()) {
          const a = socket.deserializeAttachment() || {};
          if (a.kind === "game") count++;
        }
        if (count === roomMaxPlayers) {
          this.broadcastJson({
            type: "room_full",
            map: roomMap,
            mode: roomMode,
            players: count,
            targetPlayers: roomMaxPlayers,
          }, null);
        }
      }
    } else {
      try {
        server.send(JSON.stringify({
          type: "voice_ready",
          roomCode: expectedRoom,
          playerId,
          slot,
          serverTime: Date.now(),
        }));
      } catch {}
    }

    return new Response(null, { status: 101, webSocket: client });
  }

  async webSocketMessage(ws, message) {
    const sender = ws.deserializeAttachment() || {};

    if (typeof message === "string") {
      if (sender.kind !== "game" || message.length > 32768) return;

      let parsed;
      try {
        parsed = JSON.parse(message);
      } catch {
        return;
      }
      if (!parsed || typeof parsed !== "object") return;

      if (parsed.type === "ci_ready") {
        if (sender.kind !== "game") return;

        const updated = { ...sender, ciReady: true };
        ws.serializeAttachment(updated);

        let readyCount = 0;
        let target = Number(sender.targetPlayers || MAX_PLAYERS);
        if (target < 1 || target > MAX_PLAYERS) target = MAX_PLAYERS;

        for (const socket of this.ctx.getWebSockets()) {
          const a = socket.deserializeAttachment() || {};
          if (a.kind === "game" && a.ciReady) readyCount++;
        }

        if (readyCount >= target) {
          this.broadcastText(JSON.stringify({
            type: "ci_begin",
            players: target,
            serverTime: Date.now(),
          }), null, "game");
        }
        return;
      }

      if (parsed.type === "prepare_game") {
        if (sender.slot !== 1) return;

        const current = await this.ctx.storage.get([
          "map", "worldRevision",
        ]);
        const authoritativeMap = sanitizeMap(current.get("map") || sender.map);
        const nextRevision = Number(current.get("worldRevision") || 0) + 1;

        await this.ctx.storage.put({
          worldPhase: "preparing",
          worldRevision: nextRevision,
        });

        parsed.map = authoritativeMap;
        parsed.worldPhase = "preparing";
        parsed.worldRevision = nextRevision;
      } else if (parsed.type === "server_ready") {
        if (sender.slot !== 1) return;

        const current = await this.ctx.storage.get([
          "map", "worldRevision",
        ]);
        const authoritativeMap = sanitizeMap(current.get("map") || sender.map);
        const revision = Number(current.get("worldRevision") || 0);

        await this.ctx.storage.put({ worldPhase: "live" });

        parsed.map = authoritativeMap;
        parsed.worldPhase = "live";
        parsed.worldRevision = revision;
      }

      if (parsed.type === "client_ready") {
        parsed.map = sanitizeMap(sender.map);
      }

      parsed.playerId = sender.playerId;
      parsed.slot = sender.slot;
      parsed.serverTime = Date.now();
      this.broadcastText(JSON.stringify(parsed), ws, "game");
      return;
    }

    if (!(message instanceof ArrayBuffer)) return;

    if (sender.kind === "voice") {
      const bytes = new Uint8Array(message);
      if (bytes.length > MAX_VOICE_PACKET || !isVoicePacket(bytes)) return;

      // Never trust the player slot carried by the client microphone packet.
      // Bind voice identity to the already-authenticated room WebSocket slot.
      const forwarded = new Uint8Array(bytes.length);
      forwarded.set(bytes);
      forwarded[4] = sender.slot;
      this.broadcastBinary(forwarded.buffer, ws, "voice");
      return;
    }

    if (sender.kind !== "game") return;

    const bytes = new Uint8Array(message);
    if (!isGamePacket(bytes)) return;
    if (bytes.length > GAME_HEADER_BYTES + MAX_GAME_DATAGRAM) return;

    const destinationSlot = bytes[4];
    if (destinationSlot < 1 || destinationSlot > MAX_PLAYERS) return;
    if (destinationSlot === sender.slot) return;

    // Gameplay is a strict server-authoritative star:
    //   clients (2..4) -> host/server (1)
    //   host/server (1) -> clients (2..4)
    // Never relay gameplay directly from one non-host client to another.
    if (sender.slot !== 1 && destinationSlot !== 1) return;

    const forwarded = new Uint8Array(bytes.length);
    forwarded.set(bytes);
    forwarded[4] = sender.slot;

    for (const socket of this.ctx.getWebSockets()) {
      const a = socket.deserializeAttachment() || {};
      if (a.kind !== "game" || a.slot !== destinationSlot) continue;
      try { socket.send(forwarded.buffer); } catch {}
      break;
    }
  }

  webSocketClose(ws) {
    const sender = ws.deserializeAttachment() || {};
    if (sender.kind === "game") {
      this.broadcastJson(
        { type: "player_left", playerId: sender.playerId, slot: sender.slot },
        ws,
      );
    }
  }

  webSocketError() {}

  broadcastJson(value, except) {
    this.broadcastText(
      JSON.stringify({ ...value, serverTime: Date.now() }),
      except,
      "game",
    );
  }

  broadcastText(text, except, kind) {
    for (const socket of this.ctx.getWebSockets()) {
      if (socket === except) continue;
      const a = socket.deserializeAttachment() || {};
      if (a.kind !== kind) continue;
      try { socket.send(text); } catch {}
    }
  }

  broadcastBinary(buffer, except, kind) {
    for (const socket of this.ctx.getWebSockets()) {
      if (socket === except) continue;
      const a = socket.deserializeAttachment() || {};
      if (a.kind !== kind) continue;
      try { socket.send(buffer); } catch {}
    }
  }
}
