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

# Wine's x86_64 Unix side expects a few glibc symbols that Android/Bionic
# does not export with glibc names. Route those through Box64 wrappers instead
# of resolving them directly from Bionic.
python3 - "$SRC" <<'PY'
from pathlib import Path
import sys

src = Path(sys.argv[1])

libc_h = src / "src/wrapped/wrappedlibc_private.h"
s = libc_h.read_text()
for old, new in (
    ("GO(__errno_location, pFv)", "GOM(__errno_location, pFEv)"),
    ("GO(__xpg_basename, pFp)", "GOM(__xpg_basename, pFEp)"),
):
    if old not in s:
        raise SystemExit(f"Box64 libc wrapper anchor missing: {old}")
    s = s.replace(old, new, 1)
libc_h.write_text(s)

libc_c = src / "src/wrapped/wrappedlibc.c"
s = libc_c.read_text()
anchor = "EXPORT uintptr_t my_error_print_progname = 0;\n"
if anchor not in s:
    raise SystemExit("Box64 wrappedlibc insertion anchor missing")
shim = r'''
/* XZIEL_ANDROID_GLIBC_LIBC_SHIMS */
EXPORT void* my___errno_location(x64emu_t* emu)
{
    (void)emu;
    return &errno;
}

EXPORT char* my___xpg_basename(x64emu_t* emu, char* path)
{
    (void)emu;
    if(!path || !*path)
        return path;
    if(path[0]=='/' && path[1]=='\0')
        return path;

    char* end = path + strlen(path) - 1;
    while(end > path && *end == '/') {
        *end = '\0';
        --end;
    }

    char* slash = strrchr(path, '/');
    return slash ? slash + 1 : path;
}

'''
s = s.replace(anchor, anchor + shim, 1)
libc_c.write_text(s)

librt_h = src / "src/wrapped/wrappedlibrt_private.h"
s = librt_h.read_text()
for old, new in (
    ("GO(shm_open, iFpOu)", "GOM(shm_open, iFEpOu)"),
    ("GO(shm_unlink, iFp)", "GOM(shm_unlink, iFEp)"),
):
    if old not in s:
        raise SystemExit(f"Box64 librt wrapper anchor missing: {old}")
    s = s.replace(old, new, 1)
librt_h.write_text(s)

librt_c = src / "src/wrapped/wrappedlibrt.c"
s = librt_c.read_text()
anchor = "const char* librtName = \"librt.so.1\";\n"
if anchor not in s:
    raise SystemExit("Box64 wrappedlibrt insertion anchor missing")
shim = r'''
/* XZIEL_ANDROID_GLIBC_SHM_SHIMS */
#ifdef ANDROID
EXPORT int my_shm_open(x64emu_t* emu, const char* name, int oflag, uint32_t mode)
{
    (void)emu; (void)name; (void)oflag; (void)mode;
    errno = ENOSYS;
    return -1;
}

EXPORT int my_shm_unlink(x64emu_t* emu, const char* name)
{
    (void)emu; (void)name;
    errno = ENOSYS;
    return -1;
}
#endif

'''
s = s.replace(anchor, anchor + shim, 1)
librt_c.write_text(s)

print("XZIEL_BOX64_ANDROID_GLIBC_SYMBOL_SHIMS_PATCHED")
PY

grep -q 'XZIEL_ANDROID_GLIBC_LIBC_SHIMS' "$SRC/src/wrapped/wrappedlibc.c"
grep -q 'XZIEL_ANDROID_GLIBC_SHM_SHIMS' "$SRC/src/wrapped/wrappedlibrt.c"
grep -q 'GOM(__errno_location, pFEv)' "$SRC/src/wrapped/wrappedlibc_private.h"
grep -q 'GOM(__xpg_basename, pFEp)' "$SRC/src/wrapped/wrappedlibc_private.h"
grep -q 'GOM(shm_open, iFEpOu)' "$SRC/src/wrapped/wrappedlibrt_private.h"
echo "XZIEL_BOX64_ANDROID_GLIBC_SYMBOL_SHIMS_GREEN"

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
grep -Fq 'my___libc_start_main' "$DIST/box64-pie.dynsym.txt"
echo "XZIEL_BOX64_GLIBC_START_MAIN_DYNSYM_GREEN"

echo "XZIEL_BOX64_PIE=$OUT/box64-pie" >> "$GITHUB_ENV"
echo "XZIEL_BOX64_ANDROID_PIE_INTERPRETER_GREEN path=$OUT/box64-pie"
