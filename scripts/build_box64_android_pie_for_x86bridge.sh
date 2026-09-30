#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
BUILD="$ROOT/build/box64-android-pie"
SRC="$BUILD/src"
OUT="$BUILD/out"
DIST="$ROOT/dist/android-x86bridge-smoke"

rm -rf "$BUILD"
mkdir -p "$BUILD" "$OUT" "$DIST"

ANDROID_HOME="${ANDROID_HOME:-/usr/local/lib/android/sdk}"
export ANDROID_HOME
export ANDROID_SDK_ROOT="$ANDROID_HOME"
SDKMANAGER="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"
if [[ ! -x "$SDKMANAGER" ]]; then
  SDKMANAGER="$(find "$ANDROID_HOME/cmdline-tools" -type f -name sdkmanager | sort -V | tail -n1)"
fi
test -x "$SDKMANAGER"
yes | "$SDKMANAGER" --licenses >/dev/null || true
"$SDKMANAGER" "ndk;26.1.10909125" >/dev/null

NDK="$ANDROID_HOME/ndk/26.1.10909125"
HOST="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin"
CC="$HOST/aarch64-linux-android31-clang"
CXX="$HOST/aarch64-linux-android31-clang++"
test -x "$CC"
test -x "$CXX"

git clone --depth 1 --branch v0.4.4 https://github.com/ptitSeb/box64.git "$SRC"

# XZIEL x86-bridge compatibility:
# Upstream Box64's ANDROID entrypoint only exports my___libc_init(), while
# Winlator's x86_64 Wine guest is glibc-linked and requires __libc_start_main.
# Keep the Android entrypoint and also expose the normal glibc start-main shim.
python3 - "$SRC/src/emu/entrypoint.c" <<'PY'
from pathlib import Path
import re, sys

p = Path(sys.argv[1])
s = p.read_text()

m = re.search(
    r'(#else\n)(EXPORT int32_t my___libc_start_main\(.*?\n\}\n)(#ifdef BOX32)',
    s,
    flags=re.S,
)
if not m:
    raise SystemExit("Could not locate Box64 glibc __libc_start_main implementation")

glibc_start = m.group(2)
marker = "/* XZIEL_ANDROID_GLIBC_START_MAIN */"
if marker not in s:
    inject = marker + "\n" + glibc_start
    s = s[:m.start(1)] + inject + m.group(1) + s[m.start(2):]

p.write_text(s)
PY

grep -q 'XZIEL_ANDROID_GLIBC_START_MAIN' "$SRC/src/emu/entrypoint.c"
grep -q 'EXPORT int32_t my___libc_start_main' "$SRC/src/emu/entrypoint.c"
echo "XZIEL_BOX64_ANDROID_GLIBC_START_MAIN_PATCHED"

cmake -S "$SRC" -B "$BUILD/cmake" \
  -DCMAKE_C_COMPILER="$CC" \
  -DCMAKE_CXX_COMPILER="$CXX" \
  -DANDROID=1 \
  -DARM_DYNAREC=0 \
  -DBAD_SIGNAL=1 \
  -DNOLOADADDR=ON \
  -DCMAKE_BUILD_TYPE=Release \
  -DHAVE_TRACE=0 \
  -DSTATICBUILD=0 \
  -DBOX32=0 \
  -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
  -DCMAKE_C_FLAGS="-fPIE" \
  -DCMAKE_EXE_LINKER_FLAGS="-pie -Wl,--export-dynamic"

cmake --build "$BUILD/cmake" --target box64 -j2

BOX64="$BUILD/cmake/box64"
test -s "$BOX64"
cp "$BOX64" "$OUT/box64-pie"
chmod 755 "$OUT/box64-pie"

file "$OUT/box64-pie" | tee "$DIST/box64-pie.file.txt"
readelf -h "$OUT/box64-pie" | tee "$DIST/box64-pie.readelf-h.txt"
readelf -l "$OUT/box64-pie" | tee "$DIST/box64-pie.readelf-l.txt"
readelf --dyn-syms -W "$OUT/box64-pie" | tee "$DIST/box64-pie.dynsym.txt"
sha256sum "$OUT/box64-pie" | tee "$DIST/box64-pie.sha256"

grep -Eq 'Type:[[:space:]]+DYN' "$DIST/box64-pie.readelf-h.txt"
grep -Eq '[[:space:]]my___libc_start_main "$DIST/box64-pie.dynsym.txt"
echo "XZIEL_BOX64_GLIBC_START_MAIN_DYNSYM_GREEN"

echo "XZIEL_BOX64_PIE=$OUT/box64-pie" >> "$GITHUB_ENV"
echo "XZIEL_BOX64_ANDROID_PIE_INTERPRETER_GREEN path=$OUT/box64-pie"
