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
sudo apt-get install -y gcc-aarch64-linux-gnu libc6-dev-arm64-cross >/dev/null

git clone --depth 1 --branch v0.4.4 https://github.com/ptitSeb/box64.git "$SRC"

# Upstream STATICBUILD forces "-static" after command-line CMake flags are read.
# For the x86 Android bridge we specifically need ET_DYN static PIE, so override
# that internal assignment before configure.
python3 - "$SRC/CMakeLists.txt" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()
old = "set(CMAKE_EXE_LINKER_FLAGS -static)"
new = 'set(CMAKE_EXE_LINKER_FLAGS "-static-pie")'
if old not in s:
    raise SystemExit("Box64 STATICBUILD linker flag anchor missing")
p.write_text(s.replace(old, new, 1))
print("XZIEL_BOX64_STATICBUILD_STATIC_PIE_PATCHED")
PY

# Android's x86 native bridge validates ARM64 ELF TLS using Bionic rules.
# Force at least one native TLS object to 64-byte alignment so PT_TLS p_align
# becomes >= 0x40 instead of the glibc default 0x10.
python3 - "$SRC" <<'PY'
from pathlib import Path
import sys

src = Path(sys.argv[1])
p = src / "src/os/os_linux.c"
text = p.read_text(encoding="utf-8")
old = "static __thread char native_name[500] = { 0 };"
new = "static __thread char native_name[500] __attribute__((aligned(64))) = { 0 };"
if old not in text:
    raise SystemExit("Box64 TLS alignment anchor missing")
p.write_text(text.replace(old, new, 1), encoding="utf-8")
print("XZIEL_BOX64_TLS_SOURCE_ALIGN64_PATCHED")
PY

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
  -DSTATICBUILD=ON \
  -DBOX32=OFF \
  -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
  -DCMAKE_C_FLAGS="-fPIE" \
  -DCMAKE_EXE_LINKER_FLAGS="-static-pie"

cmake --build "$BUILD/cmake" --target box64 -j2

BOX64="$BUILD/cmake/box64"
test -s "$BOX64"
cp "$BOX64" "$OUT/box64-glibc-pie"
chmod 755 "$OUT/box64-glibc-pie"

# Static PIE must not depend on Android/Bionic or on a runtime ELF interpreter.
# That lets ndk_translation validate a PIE executable while Box64 itself keeps
# the glibc ABI Winlator expects.
file "$OUT/box64-glibc-pie" | tee "$DIST/box64-glibc-pie.file.txt"
readelf -h "$OUT/box64-glibc-pie" | tee "$DIST/box64-glibc-pie.readelf-h.txt"
readelf -l "$OUT/box64-glibc-pie" | tee "$DIST/box64-glibc-pie.readelf-l.txt"
readelf -lW "$OUT/box64-glibc-pie" | tee "$DIST/box64-glibc-pie.readelf-lw.txt"
readelf -d "$OUT/box64-glibc-pie" | tee "$DIST/box64-glibc-pie.readelf-d.txt" || true
sha256sum "$OUT/box64-glibc-pie" | tee "$DIST/box64-glibc-pie.sha256"

grep -Eq 'Type:[[:space:]]+DYN' "$DIST/box64-glibc-pie.readelf-h.txt"
if grep -q 'INTERP' "$DIST/box64-glibc-pie.readelf-l.txt"; then
  echo "XZIEL_BOX64_STATIC_PIE_HAS_INTERP" >&2
  exit 73
fi
if grep -q '(NEEDED)' "$DIST/box64-glibc-pie.readelf-d.txt"; then
  echo "XZIEL_BOX64_STATIC_PIE_HAS_NEEDED" >&2
  exit 74
fi
echo "XZIEL_BOX64_STATIC_PIE_LINK_GREEN"

tls_align_hex="$(awk '$1=="TLS"{print $NF; exit}' "$DIST/box64-glibc-pie.readelf-lw.txt")"
test -n "$tls_align_hex"
tls_align_hex="${tls_align_hex#0x}"
tls_align_dec=$((16#$tls_align_hex))
echo "XZIEL_BOX64_TLS_ALIGN bytes=$tls_align_dec hex=0x$tls_align_hex"
if (( tls_align_dec < 64 )); then
  echo "XZIEL_BOX64_TLS_ALIGN_TOO_SMALL bytes=$tls_align_dec" >&2
  exit 72
fi
echo "XZIEL_BOX64_TLS_ALIGN64_GREEN"

echo "XZIEL_BOX64_PIE=$OUT/box64-glibc-pie" >> "$GITHUB_ENV"
echo "XZIEL_BOX64_GLIBC_STATIC_PIE_GREEN dynarec=off path=$OUT/box64-glibc-pie"
