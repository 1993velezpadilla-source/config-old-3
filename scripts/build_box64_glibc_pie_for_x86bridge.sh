#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
BUILD="$ROOT/build/box64-glibc-pie"
SRC="$BUILD/src"
OUT="$BUILD/out"
DIST="$ROOT/dist/android-x86bridge-smoke"

rm -rf "$BUILD"
mkdir -p "$BUILD" "$OUT" "$DIST"

sudo apt-get update >/dev/null
sudo apt-get install -y gcc-aarch64-linux-gnu patchelf >/dev/null

git clone --depth 1 --branch v0.4.4 https://github.com/ptitSeb/box64.git "$SRC"

# CI-only bridge build:
# - glibc/Winlator ABI, matching the shipped runtime
# - PIE so Android x86 native-bridge accepts the ARM64 executable
# - dynarec disabled to avoid nested AArch64 JIT execution under ndk_translation
cmake -S "$SRC" -B "$BUILD/cmake" \
  -DCMAKE_C_COMPILER=aarch64-linux-gnu-gcc \
  -DARM64=ON \
  -DWINLATOR_GLIBC=ON \
  -DARM_DYNAREC=OFF \
  -DBAD_SIGNAL=ON \
  -DNOLOADADDR=ON \
  -DCMAKE_BUILD_TYPE=Release \
  -DHAVE_TRACE=OFF \
  -DSTATICBUILD=OFF \
  -DBOX32=OFF \
  -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
  -DCMAKE_C_FLAGS="-fPIE" \
  -DCMAKE_EXE_LINKER_FLAGS="-pie"

cmake --build "$BUILD/cmake" --target box64 -j2

BOX64="$BUILD/cmake/box64"
test -s "$BOX64"
cp "$BOX64" "$OUT/box64-glibc-pie"
chmod 755 "$OUT/box64-glibc-pie"

# Match the rewritten XZIEL runtime sandbox exactly.
XZIEL_INTERP="/data/data/com.xzielapp/files/rootfs/lib/ld-linux-aarch64.so.1"
XZIEL_RPATH="/data/data/com.xzielapp/files/rootfs/lib"
patchelf --set-interpreter "$XZIEL_INTERP" "$OUT/box64-glibc-pie"
patchelf --set-rpath "$XZIEL_RPATH" "$OUT/box64-glibc-pie"

file "$OUT/box64-glibc-pie" | tee "$DIST/box64-glibc-pie.file.txt"
readelf -h "$OUT/box64-glibc-pie" | tee "$DIST/box64-glibc-pie.readelf-h.txt"
readelf -l "$OUT/box64-glibc-pie" | tee "$DIST/box64-glibc-pie.readelf-l.txt"
readelf -d "$OUT/box64-glibc-pie" | tee "$DIST/box64-glibc-pie.readelf-d.txt" || true
sha256sum "$OUT/box64-glibc-pie" | tee "$DIST/box64-glibc-pie.sha256"

grep -Eq 'Type:[[:space:]]+DYN' "$DIST/box64-glibc-pie.readelf-h.txt"
grep -q "$XZIEL_INTERP" "$DIST/box64-glibc-pie.readelf-l.txt"
grep -q "$XZIEL_RPATH" "$DIST/box64-glibc-pie.readelf-d.txt"

echo "XZIEL_BOX64_PIE=$OUT/box64-glibc-pie" >> "$GITHUB_ENV"
echo "XZIEL_BOX64_GLIBC_PIE_GREEN dynarec=off path=$OUT/box64-glibc-pie"
