#!/usr/bin/env bash
set -euo pipefail
ROOT="${XZIEL_TOOL_ROOT:-$PWD/.xziel-tools}"
BIN="$ROOT/bin"
CACHE="$ROOT/cache"
SRC="$ROOT/src"
BUILD="$ROOT/build"
mkdir -p "$BIN" "$CACHE" "$SRC" "$BUILD" "$ROOT/include" "$ROOT/lib"

download() {
  local url="$1" dst="$2"
  if [[ ! -s "$dst" ]]; then
    echo "[XZIEL] download $url"
    curl -L --fail --retry 4 --retry-delay 2 "$url" -o "$dst"
  fi
}

echo "[XZIEL] tool root: $ROOT"

GLTFPACK_ZIP="$CACHE/gltfpack-ubuntu-v1.3.zip"
download "https://github.com/zeux/meshoptimizer/releases/download/v1.3/gltfpack-ubuntu.zip" "$GLTFPACK_ZIP"
rm -rf "$BUILD/gltfpack"
mkdir -p "$BUILD/gltfpack"
unzip -q -o "$GLTFPACK_ZIP" -d "$BUILD/gltfpack"
GLTFPACK_BIN="$(find "$BUILD/gltfpack" -type f -name gltfpack -print -quit)"
test -n "$GLTFPACK_BIN"
install -m 0755 "$GLTFPACK_BIN" "$BIN/gltfpack"

KTX_ARCHIVE="$CACHE/KTX-Software-4.4.2-Linux-x86_64.tar.bz2"
download "https://github.com/KhronosGroup/KTX-Software/releases/download/v4.4.2/KTX-Software-4.4.2-Linux-x86_64.tar.bz2" "$KTX_ARCHIVE"
rm -rf "$ROOT/ktx"
mkdir -p "$ROOT/ktx"
tar -xjf "$KTX_ARCHIVE" -C "$ROOT/ktx"
cat > "$BIN/ktx" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KTX_EXE="$(find "$ROOT/ktx" -type f -path '*/bin/ktx' -print -quit)"
if [[ -z "$KTX_EXE" ]]; then
  echo "XZIEL_KTX_NOT_FOUND" >&2
  exit 2
fi
KTX_PREFIX="$(cd "$(dirname "$KTX_EXE")/.." && pwd)"
export LD_LIBRARY_PATH="$KTX_PREFIX/lib:$KTX_PREFIX/lib64:${LD_LIBRARY_PATH:-}"
exec "$KTX_EXE" "$@"
EOF
chmod +x "$BIN/ktx"

RECAST_ARCHIVE="$CACHE/recastnavigation-v1.6.0.tar.gz"
download "https://github.com/recastnavigation/recastnavigation/archive/refs/tags/v1.6.0.tar.gz" "$RECAST_ARCHIVE"
rm -rf "$SRC/recastnavigation" "$BUILD/recastnavigation" "$ROOT/recast"
mkdir -p "$SRC/recastnavigation"
tar -xzf "$RECAST_ARCHIVE" -C "$SRC/recastnavigation" --strip-components=1
cmake -S "$SRC/recastnavigation" -B "$BUILD/recastnavigation" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$ROOT/recast" \
  -DRECASTNAVIGATION_DEMO=OFF \
  -DRECASTNAVIGATION_TESTS=OFF \
  -DRECASTNAVIGATION_EXAMPLES=OFF
cmake --build "$BUILD/recastnavigation" --parallel
cmake --install "$BUILD/recastnavigation"

# XZIEL single-tile Recast -> Detour navmesh baker.
if [[ -f "tools/xziel_toolchain/xziel_navmesh_bake.cpp" ]]; then
  c++ -std=c++17 -O3 -DNDEBUG \
    -I"$ROOT/recast/include/recastnavigation" \
    tools/xziel_toolchain/xziel_navmesh_bake.cpp \
    "$ROOT/recast/lib/libRecast.a" \
    "$ROOT/recast/lib/libDetour.a" \
    -o "$BIN/xziel-navmesh-bake"
fi

# Optional connectivity verifier: loads the emitted Detour navbin, snaps named
# probes to the mesh, then requires real paths between consecutive probes.
if [[ -f "tools/xziel_toolchain/xziel_navmesh_probe.cpp" ]]; then
  c++ -std=c++17 -O3 -DNDEBUG \
    -I"$ROOT/recast/include/recastnavigation" \
    tools/xziel_toolchain/xziel_navmesh_probe.cpp \
    "$ROOT/recast/lib/libDetour.a" \
    -o "$BIN/xziel-navmesh-probe"
fi

XATLAS_SHA="f700c7790aaa030e794b52ba7791a05c085faf0c"
XATLAS_ARCHIVE="$CACHE/xatlas-$XATLAS_SHA.tar.gz"
download "https://github.com/jpcy/xatlas/archive/$XATLAS_SHA.tar.gz" "$XATLAS_ARCHIVE"
rm -rf "$SRC/xatlas"
mkdir -p "$SRC/xatlas"
tar -xzf "$XATLAS_ARCHIVE" -C "$SRC/xatlas" --strip-components=1
mkdir -p "$ROOT/include/xatlas" "$ROOT/lib"
c++ -std=c++11 -O3 -DNDEBUG -fPIC -I"$SRC/xatlas/source/xatlas" \
  -c "$SRC/xatlas/source/xatlas/xatlas.cpp" -o "$BUILD/xatlas.o"
ar rcs "$ROOT/lib/libxatlas.a" "$BUILD/xatlas.o"
install -m 0644 "$SRC/xatlas/source/xatlas/xatlas.h" "$ROOT/include/xatlas/xatlas.h"
install -m 0644 "$SRC/xatlas/source/xatlas/xatlas_c.h" "$ROOT/include/xatlas/xatlas_c.h"

cat > "$ROOT/env.sh" <<EOF
export XZIEL_TOOL_ROOT="$ROOT"
export PATH="$BIN:\$PATH"
export CMAKE_PREFIX_PATH="$ROOT/recast:\${CMAKE_PREFIX_PATH:-}"
export PKG_CONFIG_PATH="$ROOT/recast/lib/pkgconfig:\${PKG_CONFIG_PATH:-}"
EOF

echo "[XZIEL] FAST_TOOLCHAIN_READY"
"$BIN/gltfpack" -h >/dev/null 2>&1 || true
"$BIN/ktx" --version || "$BIN/ktx" version || true
test -f "$ROOT/lib/libxatlas.a"
test -x "$BIN/xziel-navmesh-bake"
if [[ -f "tools/xziel_toolchain/xziel_navmesh_probe.cpp" ]]; then
  test -x "$BIN/xziel-navmesh-probe"
fi
find "$ROOT/recast" -type f \( -name 'libRecast*' -o -name 'libDetour*' \) | head
