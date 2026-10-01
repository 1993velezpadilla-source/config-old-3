#!/usr/bin/env bash
set -euo pipefail

ROOT="${XZIEL_TOOL_ROOT:-$PWD/.xziel-tools}"
BIN="$ROOT/bin"
CACHE="$ROOT/cache"
NODE_ROOT="$ROOT/node"
mkdir -p "$BIN" "$CACHE" "$NODE_ROOT"

download() {
  local url="$1" dst="$2"
  if [[ ! -s "$dst" ]]; then
    echo "[XZIEL-ASSET] download $url"
    curl -L --fail --retry 4 --retry-delay 2 "$url" -o "$dst"
  fi
}

GLTFPACK_ZIP="$CACHE/gltfpack-ubuntu-v1.3.zip"
download "https://github.com/zeux/meshoptimizer/releases/download/v1.3/gltfpack-ubuntu.zip" "$GLTFPACK_ZIP"
rm -rf "$ROOT/asset-gltfpack"
mkdir -p "$ROOT/asset-gltfpack"
unzip -q -o "$GLTFPACK_ZIP" -d "$ROOT/asset-gltfpack"
GLTFPACK_BIN="$(find "$ROOT/asset-gltfpack" -type f -name gltfpack -print -quit)"
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
test -n "$KTX_EXE"
KTX_PREFIX="$(cd "$(dirname "$KTX_EXE")/.." && pwd)"
export LD_LIBRARY_PATH="$KTX_PREFIX/lib:$KTX_PREFIX/lib64:${LD_LIBRARY_PATH:-}"
exec "$KTX_EXE" "$@"
EOF
chmod +x "$BIN/ktx"

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "XZIEL_ASSET_CLI_REQUIRES_NODE_NPM" >&2
  exit 2
fi

npm install --prefix "$NODE_ROOT" --no-audit --no-fund --silent \
  "@gltf-transform/cli@4.5.1" \
  "gltf-validator@2.0.0-dev.3.10"

ln -sf "$NODE_ROOT/node_modules/.bin/gltf-transform" "$BIN/gltf-transform"

cat > "$ROOT/asset-env.sh" <<EOF
export XZIEL_TOOL_ROOT="$ROOT"
export PATH="$BIN:\$PATH"
export NODE_PATH="$NODE_ROOT/node_modules:\${NODE_PATH:-}"
EOF

"$BIN/gltfpack" -h >/dev/null 2>&1 || true
"$BIN/gltf-transform" --version
"$BIN/ktx" --version || "$BIN/ktx" version || true
echo "XZIEL_ASSET_CLI_READY"
