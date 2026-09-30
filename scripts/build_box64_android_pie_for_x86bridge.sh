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
    ("GO(__ctype_b_loc, pFv)", "GOM(__ctype_b_loc, pFEv)"),
    ("GO(__ctype_tolower_loc, pFv)", "GOM(__ctype_tolower_loc, pFEv)"),
    ("GO(__ctype_toupper_loc, pFv)", "GOM(__ctype_toupper_loc, pFEv)"),
    ("GO(nl_langinfo, pFi)", "GOM(nl_langinfo, pFEi)"),
):
    if old not in s:
        raise SystemExit(f"Box64 libc wrapper anchor missing: {old}")
    s = s.replace(old, new, 1)

# glibc 2.34 moved POSIX shm entry points into libc. Wine's x86_64 ntdll.so
# therefore resolves shm_open/shm_unlink against libc.so.6, not librt.so.1.
# Export the same Box64 custom wrappers from wrappedlibc too; the actual
# Android-safe implementations remain centralized in wrappedlibrt.c.
anchor = "GOM(__xpg_basename, pFEp)"
if anchor not in s:
    raise SystemExit("Box64 libc shm insertion anchor missing")
for entry in ("GOM(shm_open, iFEpOu)", "GOM(shm_unlink, iFEp)"):
    if entry not in s:
        s = s.replace(anchor, anchor + "\n" + entry, 1)
        anchor = entry
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

/*
 * Bionic does not export glibc's __ctype_*_loc ABI.  Wine's Unix-side
 * helpers use those symbols even in the C locale, so provide the glibc table
 * shape (384 entries, pointer biased by 128) with the glibc bit layout.
 */
static unsigned short xziel_ctype_b_table[384];
static int32_t xziel_ctype_tolower_table[384];
static int32_t xziel_ctype_toupper_table[384];
static const unsigned short* xziel_ctype_b_ptr = xziel_ctype_b_table + 128;
static const int32_t* xziel_ctype_tolower_ptr = xziel_ctype_tolower_table + 128;
static const int32_t* xziel_ctype_toupper_ptr = xziel_ctype_toupper_table + 128;
static int xziel_ctype_ready = 0;

static void xziel_init_ctype_tables(void)
{
    if(xziel_ctype_ready)
        return;

    for(int c = -128; c < 256; ++c) {
        int idx = c + 128;
        unsigned short f = 0;
        int lower = c;
        int upper = c;

        if(c >= 0) {
            unsigned int u = (unsigned int)c;
            if(u >= 'A' && u <= 'Z') {
                f |= 0x0100 | 0x0400 | 0x0008; /* upper|alpha|alnum */
                lower = (int)(u - 'A' + 'a');
            }
            if(u >= 'a' && u <= 'z') {
                f |= 0x0200 | 0x0400 | 0x0008; /* lower|alpha|alnum */
                upper = (int)(u - 'a' + 'A');
            }
            if(u >= '0' && u <= '9')
                f |= 0x0800 | 0x1000 | 0x0008; /* digit|xdigit|alnum */
            if((u >= 'A' && u <= 'F') || (u >= 'a' && u <= 'f'))
                f |= 0x1000; /* xdigit */

            if(u == ' ' || u == '\t')
                f |= 0x0001; /* blank */
            if(u == ' ' || u == '\t' || u == '\n' || u == '\r' || u == '\v' || u == '\f')
                f |= 0x2000; /* space */
            if(u < 0x20 || u == 0x7f)
                f |= 0x0002; /* cntrl */
            if(u >= 0x20 && u <= 0x7e)
                f |= 0x4000; /* print */
            if(u >= 0x21 && u <= 0x7e)
                f |= 0x8000; /* graph */

            if(u >= 0x21 && u <= 0x7e &&
               !((u >= 'A' && u <= 'Z') ||
                 (u >= 'a' && u <= 'z') ||
                 (u >= '0' && u <= '9')))
                f |= 0x0004; /* punct */
        }

        xziel_ctype_b_table[idx] = f;
        xziel_ctype_tolower_table[idx] = lower;
        xziel_ctype_toupper_table[idx] = upper;
    }

    xziel_ctype_ready = 1;
}

EXPORT void* my___ctype_b_loc(x64emu_t* emu)
{
    (void)emu;
    xziel_init_ctype_tables();
    return &xziel_ctype_b_ptr;
}

EXPORT void* my___ctype_tolower_loc(x64emu_t* emu)
{
    (void)emu;
    xziel_init_ctype_tables();
    return &xziel_ctype_tolower_ptr;
}

EXPORT void* my___ctype_toupper_loc(x64emu_t* emu)
{
    (void)emu;
    xziel_init_ctype_tables();
    return &xziel_ctype_toupper_ptr;
}

/*
 * glibc and Bionic use different nl_item numeric layouts. Wine asks for
 * glibc CODESET as item 0x0e; passing that value straight to Bionic returns
 * a weekday string ("Saturday") instead of the codeset.
 */
EXPORT char* my_nl_langinfo(x64emu_t* emu, int item)
{
    (void)emu;
#ifdef ANDROID
    if(item == 0x0e)
        return "UTF-8";
#endif
    return nl_langinfo((nl_item)item);
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
include_anchor = '#include <errno.h>\n'
if include_anchor not in s:
    raise SystemExit("Box64 wrappedlibrt include anchor missing")
for inc in ('#include <fcntl.h>\n', '#include <sys/stat.h>\n', '#include <unistd.h>\n'):
    if inc not in s:
        s = s.replace(include_anchor, include_anchor + inc, 1)
        include_anchor = inc
anchor = "const char* librtName = \"librt.so.1\";\n"
if anchor not in s:
    raise SystemExit("Box64 wrappedlibrt insertion anchor missing")
shim = r'''
/* XZIEL_ANDROID_GLIBC_SHM_SHIMS */
#ifdef ANDROID
static int xziel_android_shm_path(const char* name, char* out, size_t out_size)
{
    const char* tmpdir = getenv("TMPDIR");
    if(!tmpdir || !*tmpdir)
        tmpdir = "/data/data/com.xzielapp/files/rootfs/tmp";

    while(name && *name == '/')
        ++name;
    if(!name || !*name) {
        errno = EINVAL;
        return -1;
    }

    char dir[1024];
    int n = snprintf(dir, sizeof(dir), "%s/shm", tmpdir);
    if(n < 0 || (size_t)n >= sizeof(dir)) {
        errno = ENAMETOOLONG;
        return -1;
    }
    if(mkdir(dir, 0700) != 0 && errno != EEXIST)
        return -1;

    n = snprintf(out, out_size, "%s/%s", dir, name);
    if(n < 0 || (size_t)n >= out_size) {
        errno = ENAMETOOLONG;
        return -1;
    }
    return 0;
}

EXPORT int my_shm_open(x64emu_t* emu, const char* name, int oflag, uint32_t mode)
{
    (void)emu;
    char path[1536];
    if(xziel_android_shm_path(name, path, sizeof(path)) != 0)
        return -1;
    return open(path, oflag, (mode_t)mode);
}

EXPORT int my_shm_unlink(x64emu_t* emu, const char* name)
{
    (void)emu;
    char path[1536];
    if(xziel_android_shm_path(name, path, sizeof(path)) != 0)
        return -1;
    return unlink(path);
}
#endif

'''
s = s.replace(anchor, anchor + shim, 1)
librt_c.write_text(s)

print("XZIEL_BOX64_ANDROID_GLIBC_SYMBOL_SHIMS_PATCHED file_backed_shm=1")
PY

grep -q 'XZIEL_ANDROID_GLIBC_LIBC_SHIMS' "$SRC/src/wrapped/wrappedlibc.c"
grep -q 'XZIEL_ANDROID_GLIBC_SHM_SHIMS' "$SRC/src/wrapped/wrappedlibrt.c"
grep -q 'GOM(__errno_location, pFEv)' "$SRC/src/wrapped/wrappedlibc_private.h"
grep -q 'GOM(__xpg_basename, pFEp)' "$SRC/src/wrapped/wrappedlibc_private.h"
grep -q 'GOM(__ctype_b_loc, pFEv)' "$SRC/src/wrapped/wrappedlibc_private.h"
grep -q 'GOM(__ctype_tolower_loc, pFEv)' "$SRC/src/wrapped/wrappedlibc_private.h"
grep -q 'GOM(__ctype_toupper_loc, pFEv)' "$SRC/src/wrapped/wrappedlibc_private.h"
grep -q 'my___ctype_b_loc' "$SRC/src/wrapped/wrappedlibc.c"
grep -q 'my___ctype_tolower_loc' "$SRC/src/wrapped/wrappedlibc.c"
grep -q 'my___ctype_toupper_loc' "$SRC/src/wrapped/wrappedlibc.c"
grep -q 'GOM(nl_langinfo, pFEi)' "$SRC/src/wrapped/wrappedlibc_private.h"
grep -q 'my_nl_langinfo' "$SRC/src/wrapped/wrappedlibc.c"
echo "XZIEL_BOX64_ANDROID_GLIBC_CTYPE_GREEN"
echo "XZIEL_BOX64_ANDROID_GLIBC_LANGINFO_GREEN"
grep -q 'GOM(shm_open, iFEpOu)' "$SRC/src/wrapped/wrappedlibc_private.h"
grep -q 'GOM(shm_unlink, iFEp)' "$SRC/src/wrapped/wrappedlibc_private.h"
grep -q 'GOM(shm_open, iFEpOu)' "$SRC/src/wrapped/wrappedlibrt_private.h"
echo "XZIEL_BOX64_ANDROID_GLIBC34_SHM_IN_LIBC_GREEN"
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
