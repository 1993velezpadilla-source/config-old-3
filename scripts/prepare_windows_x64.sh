#!/usr/bin/env bash
# CI probe: validates the self-contained Windows x64 package intended for Winlator.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build/xziel-win64"
DEPS="$BUILD/deps"
DOWNLOADS="$BUILD/downloads"
DATA_WORK="$BUILD/data"
DIST="$BUILD/dist/XZIEL-WIN64"

TRIPLET="${XZIEL_WIN64_TRIPLET:-x86_64-w64-mingw32}"
SDL2_VER="${SDL2_VER:-2.32.10}"
SDL2_MIXER_VER="${SDL2_MIXER_VER:-2.8.2}"
XZIEL_MAX_AI_COUNT="${XZIEL_MAX_AI_COUNT:-96}"

rm -rf "$BUILD"
mkdir -p "$DEPS" "$DOWNLOADS" "$DATA_WORK" "$DIST"

echo "==> XZIEL-WIN64: cloning engine/gameplay sources"
git clone --depth 1 https://github.com/nzp-team/vril-engine.git "$DEPS/vril"
git clone --depth 1 https://github.com/nzp-team/quakec.git "$DEPS/quakec"

echo "==> XZIEL-WIN64: applying the proven Xziel engine patch chain"
# The Android-only sections are compile-time guarded; using the same patch
# dependency order keeps the shared gameplay/data ABI aligned. Android-only
# versioned touch-HUD patches are intentionally omitted for the first Winlator
# gate; Winlator provides input mapping until the EXE runtime is proven.
python3 "$ROOT/scripts/patch_vril_android.py" "$DEPS/vril"
python3 "$ROOT/scripts/patch_vril_weaponhud.py" "$DEPS/vril"
python3 "$ROOT/scripts/patch_vril_combatfx.py" "$DEPS/vril"
python3 "$ROOT/scripts/patch_vril_modern_movement.py" "$DEPS/vril"
python3 "$ROOT/scripts/patch_vril_camera_feel.py" "$DEPS/vril"
python3 "$ROOT/scripts/patch_vril_animation_feel.py" "$DEPS/vril"
python3 "$ROOT/scripts/patch_vril_sanctum_staticmesh.py" "$DEPS/vril"

echo "==> XZIEL-WIN64: applying Xziel gameplay patches"
python3 -m pip install --quiet colorama==0.4.6 fastcrc==0.3.0 pandas==2.1.4 cairosvg==2.8.2
python3 "$ROOT/scripts/patch_quakec_mobile.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_combatfx.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_modern_movement.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_mobile_v021.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_mobile_v022.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_mobile_v024.py" "$DEPS/quakec"
if [[ "${XZIEL_NACHT_BENCHMARK:-1}" == "1" ]]; then
    python3 "$ROOT/scripts/patch_quakec_nacht_benchmark.py" "$DEPS/quakec"
fi
chmod +x "$DEPS/quakec/bin/fteqcc-cli-lin" "$DEPS/quakec/tools/qc-compiler-gnu.sh"
(
    cd "$DEPS/quakec"
    bash tools/qc-compiler-gnu.sh
)

echo "==> XZIEL-WIN64: preparing MinGW SDL runtime"
MINGW_DEPS="$BUILD/mingw-deps"
mkdir -p "$MINGW_DEPS"
(
    cd "$DOWNLOADS"
    wget -q "https://github.com/libsdl-org/SDL/releases/download/release-${SDL2_VER}/SDL2-devel-${SDL2_VER}-mingw.tar.gz" -O SDL2.tar.gz
    wget -q "https://github.com/libsdl-org/SDL_mixer/releases/download/release-${SDL2_MIXER_VER}/SDL2_mixer-devel-${SDL2_MIXER_VER}-mingw.tar.gz" -O SDL2_mixer.tar.gz
    tar xf SDL2.tar.gz
    tar xf SDL2_mixer.tar.gz
    cp -a "SDL2-${SDL2_VER}/${TRIPLET}/." "$MINGW_DEPS/"
    cp -a "SDL2_mixer-${SDL2_MIXER_VER}/${TRIPLET}/." "$MINGW_DEPS/"
)
sed -i "s|^prefix=.*|prefix=$MINGW_DEPS|" "$MINGW_DEPS"/lib/pkgconfig/*.pc

echo "==> XZIEL-WIN64: compiling Xziel.exe"
# Keep the normal SDL desktop renderer but raise the AI ceiling for stress testing.
sed -i "s/-DMAX_AI_COUNT=24/-DMAX_AI_COUNT=${XZIEL_MAX_AI_COUNT}/" "$DEPS/vril/Makefile.sdl"
(
    cd "$DEPS/vril"
    PKG_CONFIG_PATH="$MINGW_DEPS/lib/pkgconfig" \
    PKG_CONFIG_LIBDIR="$MINGW_DEPS/lib/pkgconfig" \
    make -f Makefile.sdl WERROR=1 -j"$(nproc)" \
        BUILD="build/sdl/x86_64" \
        TARGET="build/sdl/x86_64/Xziel.exe" \
        CROSS_COMPILE="${TRIPLET}-"
)
cp "$DEPS/vril/build/sdl/x86_64/Xziel.exe" "$DIST/Xziel.exe"
cp "$MINGW_DEPS"/bin/*.dll "$DIST/"

echo "==> XZIEL-WIN64: assembling complete NZ:P/Xziel game data"
curl -fL --retry 6 --retry-delay 2 --retry-all-errors \
    https://github.com/nzp-team/assets/releases/download/newest/pc-nzp-assets.zip \
    -o "$DOWNLOADS/pc-nzp-assets.zip"
curl -fL --retry 6 --retry-delay 2 --retry-all-errors \
    https://github.com/nzp-team/quakec/releases/download/bleeding-edge/standard-nzp-qc.zip \
    -o "$DOWNLOADS/standard-nzp-qc.zip"

unzip -q "$DOWNLOADS/pc-nzp-assets.zip" -d "$DATA_WORK"
mkdir -p "$DATA_WORK/nzp"
unzip -q "$DOWNLOADS/standard-nzp-qc.zip" -d "$DATA_WORK/nzp"
python3 "$ROOT/scripts/build_xziel_icons.py" "$DATA_WORK/nzp/gfx/xziel"
cp "$DEPS/quakec/build/standard/progs.dat" "$DATA_WORK/nzp/progs.dat"
if [[ -f "$DEPS/quakec/build/standard/progs.lno" ]]; then
    cp "$DEPS/quakec/build/standard/progs.lno" "$DATA_WORK/nzp/progs.lno"
fi
cp -a "$DATA_WORK/nzp" "$DIST/nzp"

cat > "$DIST/RUN_NACHT.cmd" <<'CMD'
@echo off
cd /d "%~dp0"
Xziel.exe -basedir . +map ndu
CMD

cat > "$DIST/RUN_XZIEL.cmd" <<'CMD'
@echo off
cd /d "%~dp0"
Xziel.exe -basedir .
CMD

cat > "$DIST/WINLATOR.txt" <<'TXT'
XZIEL-WIN64 / Winlator smoke test

Executable:
  Xziel.exe

Working directory:
  the XZIEL-WIN64 folder (the folder containing Xziel.exe and nzp/)

Arguments for direct Nacht test:
  -basedir . +map ndu

Recommended first compatibility path:
  Windows x86_64 container
  Box64 enabled
  DXVK/D3D11 path if/when Xziel moves to D3D11; this current Vril prototype uses OpenGL/SDL.
  Use Winlator input mapping for the first test. Native Xziel Android touch integration comes after the EXE runtime gate passes.

Success gate:
  1. main menu or direct Nacht loads
  2. player can move/look/fire/reload
  3. zombies spawn and navigate
  4. rounds advance
  5. doors/economy/weapons work
  6. death/restart works
  7. no crash during a sustained match
TXT

mkdir -p "$DIST/licenses"
cp "$DEPS/vril/LICENSE" "$DIST/licenses/VRIL-GPL-2.0.txt"
cp "$DEPS/quakec/LICENSE" "$DIST/licenses/NZP-QUAKEC-GPL-2.0.txt"
curl -fL --retry 6 --retry-delay 2 --retry-all-errors \
    https://raw.githubusercontent.com/nzp-team/assets/main/LICENSE.md \
    -o "$DIST/licenses/NZP-ASSETS-CC-BY-SA-4.0.txt"

echo "==> XZIEL-WIN64: validation"
test -s "$DIST/Xziel.exe"
test -s "$DIST/nzp/progs.dat"
test -d "$DIST/nzp/maps"
file "$DIST/Xziel.exe"
"${TRIPLET}-objdump" -f "$DIST/Xziel.exe" | tee "$BUILD/pe-report.txt"
find "$DIST" -maxdepth 1 -type f -printf '%f\n' | sort

(
    cd "$BUILD/dist"
    zip -q -r XZIEL-WIN64-WINLATOR.zip XZIEL-WIN64
)
sha256sum "$BUILD/dist/XZIEL-WIN64-WINLATOR.zip" | tee "$BUILD/dist/XZIEL-WIN64-WINLATOR.zip.sha256"

echo "XZIEL_WIN64_PACKAGE_OK"
echo "Artifact: $BUILD/dist/XZIEL-WIN64-WINLATOR.zip"
