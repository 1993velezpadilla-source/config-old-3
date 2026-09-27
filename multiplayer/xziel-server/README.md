# XZIEL Dedicated Multiplayer Backend

Self-hosted XZIEL control plane for lobby, room codes, matchmaking, endpoint discovery, and voice relay.

Gameplay does not travel through the control WebSocket. Each match starts a headless Vril process and Android clients connect directly over Vril's native UDP transport.

## Runtime

The service expects a Linux Vril SDL binary with -dedicated support, an NZ:P basedir containing nzp/ and the same patched progs.dat as Android, a public IPv4/hostname, and an exposed UDP port range.

Example:

    ./xziel-server --listen :8080 --public-host 203.0.113.10       --vril-bin /opt/xziel/bin/nzportable --data-dir /opt/xziel/data       --port-min 26000 --port-max 26099

Put Caddy/nginx in front of port 8080 for HTTPS/WSS. The UDP game ports must remain direct.

## Compatible client routes

- POST /api/rooms/create
- WS /matchmake
- WS /game/{roomCode}
- WS /voice/{roomCode}

Dedicated rooms advertise serverMode=dedicated and endpoint=HOST:PORT. Slot 1 remains a lobby/UI identity only; it is no longer the authoritative game server.

The architecture deliberately reuses public, proven components and patterns: Vril's existing dedicated/UDP path, the self-hosted lobby/matchmaking pattern demonstrated by Producdevity/cod-boz-online, and the dedicated-session separation documented by Nakama/GameNetworkingSockets-style stacks. No new gameplay transport protocol is introduced.
