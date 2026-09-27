#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build/dedicated"
DEPS="$BUILD/deps"
DIST="$ROOT/dist/xziel-dedicated"
DATA="$DIST/data"

rm -rf "$BUILD" "$DIST"
mkdir -p "$DEPS" "$DATA"

echo "==> Installing/using upstream Vril + QuakeC"
git clone --depth 1 https://github.com/nzp-team/vril-engine.git "$DEPS/vril"
git clone --depth 1 https://github.com/nzp-team/quakec.git "$DEPS/quakec"

echo "==> Building the same Xziel QuakeC gameplay used by Android"
python3 -m pip install --quiet colorama==0.4.6 fastcrc==0.3.0 pandas==2.1.4 cairosvg==2.8.2
python3 "$ROOT/scripts/patch_quakec_mobile.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_combatfx.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_modern_movement.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_mobile_v021.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_mobile_v022.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_mobile_v024.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_multiplayer_v026.py" "$DEPS/quakec"
chmod +x "$DEPS/quakec/bin/fteqcc-cli-lin" "$DEPS/quakec/tools/qc-compiler-gnu.sh"
(
    cd "$DEPS/quakec"
    bash tools/qc-compiler-gnu.sh
)

echo "==> Assembling NZ:P server data"
curl -fL --retry 6 --retry-delay 2 --retry-all-errors \
    https://github.com/nzp-team/assets/releases/download/newest/pc-nzp-assets.zip \
    -o "$BUILD/pc-nzp-assets.zip"
curl -fL --retry 6 --retry-delay 2 --retry-all-errors \
    https://github.com/nzp-team/quakec/releases/download/bleeding-edge/standard-nzp-qc.zip \
    -o "$BUILD/standard-nzp-qc.zip"

unzip -q "$BUILD/pc-nzp-assets.zip" -d "$DATA"
mkdir -p "$DATA/nzp"
unzip -q "$BUILD/standard-nzp-qc.zip" -d "$DATA/nzp"
cp "$DEPS/quakec/build/standard/progs.dat" "$DATA/nzp/progs.dat"
if [[ -f "$DEPS/quakec/build/standard/progs.lno" ]]; then
    cp "$DEPS/quakec/build/standard/progs.lno" "$DATA/nzp/progs.lno"
fi

echo "==> Building Vril SDL Linux binary"
mkdir -p "$DIST/bin"
make -C "$DEPS/vril" -f Makefile.sdl \
    BUILD="$BUILD/vril-sdl" \
    TARGET="$DIST/bin/nzportable"
chmod +x "$DIST/bin/nzportable"

mkdir -p "$DIST/licenses"
cp "$DEPS/vril/LICENSE" "$DIST/licenses/VRIL-GPL-2.0.txt"
cp "$DEPS/quakec/LICENSE" "$DIST/licenses/NZP-QUAKEC-GPL-2.0.txt"

echo "==> Smoke-testing true headless dedicated UDP server"
SMOKE_PORT="${XZIEL_DEDICATED_SMOKE_PORT:-26990}"
LOG="$BUILD/dedicated-smoke.log"
SDL_AUDIODRIVER=dummy stdbuf -oL -eL "$DIST/bin/nzportable" \
    -dedicated 4 \
    +vid_renderer headless \
    -basedir "$DATA" \
    -port "$SMOKE_PORT" \
    +maxplayers 4 \
    +coop 1 \
    +deathmatch 0 \
    +map ndu \
    >"$LOG" 2>&1 &
PID=$!

READY=0
for _ in $(seq 1 300); do
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "==> Dedicated log before exit"
        cat "$LOG"
        echo "Dedicated process exited before UDP bind" >&2
        exit 1
    fi
    if ss -lun | awk '{print $5}' | grep -Eq ":${SMOKE_PORT}$"; then
        READY=1
        break
    fi
    sleep 0.1
done

if [[ "$READY" != "1" ]]; then
    echo "==> Dedicated process status"
    ps -o pid,ppid,stat,etime,wchan:32,cmd -p "$PID" || true
    echo "==> UDP sockets"
    ss -lunp || true
    echo "==> Dedicated log"
    cat "$LOG" || true
    kill "$PID" 2>/dev/null || true
    echo "Dedicated server never bound UDP ${SMOKE_PORT}" >&2
    exit 1
fi

echo "XZIEL_DEDICATED_UDP_GREEN port=${SMOKE_PORT}"
kill "$PID" 2>/dev/null || true
wait "$PID" 2>/dev/null || true

echo "Vril:   $(git -C "$DEPS/vril" rev-parse HEAD)"
echo "QuakeC: $(git -C "$DEPS/quakec" rev-parse HEAD)"
sha256sum "$DIST/bin/nzportable" "$DATA/nzp/progs.dat"
