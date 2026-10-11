#!/usr/bin/env bash
# Stage genuine decompiled BO1 source transiently; build Android diagnostic APK.
set -euo pipefail
SRC="$RUNNER_TEMP/bo1-original-source"
STAGE="$RUNNER_TEMP/bo1-native-staged"
APP="$RUNNER_TEMP/bo1-native-android-app"
PUBLIC="$RUNNER_TEMP/bo1-native-apk-public"
REPORT="$RUNNER_TEMP/bo1-native-apk-report"
UPSTREAM_SHA="102f6992be332610aff587e681e3180b15f395bb"
mkdir -p "$STAGE" "$APP" "$PUBLIC" "$REPORT"
git clone --depth 1 https://github.com/MisaDev4/bo1-zombies-decompiled.git "$SRC"
test "$(git -C "$SRC" rev-parse HEAD)" = "$UPSTREAM_SHA"
python3 tools/bo1_pc_engine/compat/stage_real_modules.py --upstream "$SRC" --staged "$STAGE"
cp "$STAGE/manifest.json" "$REPORT/bo1-original-math-and-assets-manifest.json"
python3 tools/bo1_pc_engine/fastfile/stage_db_file_functions.py --upstream "$SRC" --staged "$STAGE"
cp "$STAGE/manifest.json" "$REPORT/bo1-original-file-manifest.json"
python3 tools/bo1_pc_engine/ff_payload/stage_original_auth.py --upstream "$SRC" --staged "$STAGE"
cp "$STAGE/auth-extraction.json" "$REPORT/bo1-original-zlib-manifest.json"
python3 tools/bo1_pc_engine/xblocks/stage_real_alloc.py --upstream "$SRC" --staged "$STAGE"
cp "$STAGE/alloc-manifest.json" "$REPORT/bo1-original-alloc-manifest.json"
g++ -std=c++20 -O2 -I tools/bo1_pc_engine/xblocks   "$STAGE/original_bo1_db_alloc.cpp" tools/bo1_pc_engine/xblocks/bo1_alloc_posix.cpp   tools/bo1_pc_engine/xblocks/bo1_alloc_host_test.cpp   -o "$STAGE/bo1_original_alloc_test"
"$STAGE/bo1_original_alloc_test" | tee "$REPORT/bo1-original-memory-test.txt"
grep -q 'ORIGINAL_BO1_DB_ALLOCXBLOCKS_SEVEN_BLOCKS_HOST=PASS' "$REPORT/bo1-original-memory-test.txt"
SDKMANAGER="$(find "$ANDROID_HOME/cmdline-tools" -type f -name sdkmanager | sort -V | tail -n 1)"
"$SDKMANAGER" 'ndk;27.2.12479018'
NDK="$ANDROID_HOME/ndk/27.2.12479018"
N="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin"
C="$N/aarch64-linux-android26-clang++"
D="$SRC/src"
H=tools/bo1_pc_engine/compat
F=tools/bo1_pc_engine/fastfile
P=tools/bo1_pc_engine/ff_payload
J=tools/bo1_pc_engine/android_app/native
OPT="-std=c++20 -O2 -DNDEBUG -fPIC -fvisibility=hidden -ffunction-sections -fdata-sections"
"$C" $OPT -include "$H/bo1_arm64_math_compat.h" -I"$D" -I"$D/universal" -c "$STAGE/com_math_anglevectors.cpp" -o "$STAGE/orientation.o"
"$C" $OPT -include "$H/bo1_asset_unpack_compat.h" -I"$D" -I"$D/universal" -c "$STAGE/com_pack.cpp" -o "$STAGE/unpack.o"
"$C" $OPT -I"$D" -I"$D/minilzo" -c "$STAGE/minilzo.cpp" -o "$STAGE/lzo.o"
"$C" $OPT -include "$H/bo1_arm64_math_compat.h" -I"$D" -I"$D/universal" -c "$H/orientation_arm64_wrapper.cpp" -o "$STAGE/angle_bridge.o"
"$C" $OPT -include "$H/bo1_asset_unpack_compat.h" -I"$D" -I"$D/universal" -c "$H/asset_unpack_arm64_wrapper.cpp" -o "$STAGE/material_bridge.o"
"$C" $OPT -I"$D" -c "$H/lzo_arm64_wrapper.cpp" -o "$STAGE/lzo_bridge.o"
"$C" $OPT -I"$F" -I"$P" -c "$STAGE/original_bo1_db_file.cpp" -o "$STAGE/ff_file.o"
"$C" $OPT -I"$F" -I"$P" -c "$STAGE/original_bo1_db_auth_inflate.cpp" -o "$STAGE/ff_zlib.o"
"$C" $OPT -I"$F" -I"$P" -c "$F/bo1_ff_compat.cpp" -o "$STAGE/ff_posix.o"
"$C" $OPT -I"$F" -I"$P" -c "$P/bo1_ff_header_probe.cpp" -o "$STAGE/ff_header.o"
"$C" $OPT -I"$F" -I"$P" -c "$P/bo1_ff_stream_probe.cpp" -o "$STAGE/ff_stream.o"
"$C" $OPT -I"$F" -I"$P" -I tools/bo1_pc_engine/xblocks   -c "$J/bo1_android_jni.cpp" -o "$STAGE/android_jni.o"
"$C" $OPT -I tools/bo1_pc_engine/xblocks -c "$STAGE/original_bo1_db_alloc.cpp" -o "$STAGE/bo1_original_alloc.o"
"$C" $OPT -I tools/bo1_pc_engine/xblocks -c tools/bo1_pc_engine/xblocks/bo1_alloc_posix.cpp -o "$STAGE/bo1_posix_memory.o"
LIB="$STAGE/libbo1_real_original_core_arm64.so"
"$C" -shared -pthread -Wl,--gc-sections -Wl,--no-undefined "$STAGE/orientation.o" "$STAGE/unpack.o" "$STAGE/lzo.o" "$STAGE/angle_bridge.o" "$STAGE/material_bridge.o" "$STAGE/lzo_bridge.o" "$STAGE/ff_file.o" "$STAGE/ff_zlib.o" "$STAGE/ff_posix.o" "$STAGE/ff_header.o" "$STAGE/ff_stream.o" "$STAGE/android_jni.o"  "$STAGE/bo1_original_alloc.o" "$STAGE/bo1_posix_memory.o" -lz -o "$LIB"
file "$LIB" | tee "$REPORT/arm64-abi.txt"
grep -q 'ELF 64-bit' "$REPORT/arm64-abi.txt"
grep -Eqi 'ARM aarch64|ARM64' "$REPORT/arm64-abi.txt"
"$N/llvm-nm" -D "$LIB" > "$REPORT/original-module-symbols.txt"
for symbol in Java_com_bubblegum_bo1native_MainActivity_nativeSelfTest Java_com_bubblegum_bo1native_MainActivity_nativeProbeFile bo1_original_angle_vectors bo1_original_unpack_rgba bo1_original_zone_exists bo1_original_ff_payload_prefix_probe bo1_original_xblock_allocation_smoke; do
 grep -q "$symbol" "$REPORT/original-module-symbols.txt"
done
cp -a tools/bo1_pc_engine/android_app/. "$APP/"
JAR="$APP/app/src/main/jniLibs/arm64-v8a"
mkdir -p "$JAR"
cp "$LIB" "$JAR/"
readelf -d "$LIB" > "$REPORT/arm64-dynamic-libs.txt"
if grep -Fq 'libc++_shared.so' "$REPORT/arm64-dynamic-libs.txt"; then
 RUNTIME="$NDK/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/aarch64-linux-android/libc++_shared.so"
 if [ ! -r "$RUNTIME" ]; then
   RUNTIME="$NDK/sources/cxx-stl/llvm-libc++/libs/arm64-v8a/libc++_shared.so"
 fi
 if [ ! -r "$RUNTIME" ]; then
   echo "ERROR: libc++_shared.so required by BO1 .so but absent in NDK" >&2
   find "$NDK" -name libc++_shared.so | head -n 12 || true
   exit 10
 fi
 cp "$RUNTIME" "$JAR/"
 echo 'C++ shared runtime copied' >> "$REPORT/arm64-abi.txt"
fi
gradle -p "$APP" --no-daemon --console=plain :app:assembleDebug
APK="$APP/app/build/outputs/apk/debug/app-debug.apk"
test -s "$APK"
unzip -l "$APK" > "$REPORT/apk-entries.txt"
grep -q 'lib/arm64-v8a/libbo1_real_original_core_arm64.so' "$REPORT/apk-entries.txt"
grep -q 'classes.dex' "$REPORT/apk-entries.txt"
grep -q 'AndroidManifest.xml' "$REPORT/apk-entries.txt"
OUT="$PUBLIC/BO1_Original_ARM64_NATIVE_PORT_DIAGNOSTIC_NOT_PLAYABLE.apk"
cp "$APK" "$OUT"
sha256sum "$OUT" | tee "$REPORT/apk-sha256.txt"
TOOLS="$ANDROID_HOME/build-tools/35.0.0"
if [ -x "$TOOLS/apksigner" ]; then "$TOOLS/apksigner" verify --verbose "$OUT" | tee "$REPORT/apksigner.txt"; fi
if [ -x "$TOOLS/aapt" ]; then "$TOOLS/aapt" dump badging "$OUT" | head -n 20 > "$REPORT/apk-badging.txt"; fi
cat > "$REPORT/README.md" <<EOF
# Black Ops 1 recovered C++ subsystem: Android ARM64 native APK
Source MisaDev4/bo1-zombies-decompiled @ $UPSTREAM_SHA

This is a REAL installable Android APK for testing native C++ integration.
IT IS NOT A PLAYABLE BLACK OPS 1 GAME.

App can execute original engine camera/color algorithms and locally inspect
user-owned .ff archives with recovered BO1 zlib functions.
No commercial game assets embedded, no emulation, no invented FPS game.

Android build and signature verification PASS does NOT prove installation
on actual user Pixel Fold. Device boot/JNI run needs on-device verification.

$(cat "$REPORT/apk-sha256.txt")

FULL ENGINE: NOT PORTED. KINO: NOT RUNNING.
Main blockers: secure .ff, XAsset stream relocation, x86 pointer layouts, DirectX9
renderer, input/audio, gameplay loop.
EOF
cat "$REPORT/README.md" >> "$GITHUB_STEP_SUMMARY"
echo 'BO1_NATIVE_DIAGNOSTIC_APK_BUILT=true' >> "$GITHUB_STEP_SUMMARY"
echo 'BO1_PLAYABLE_GAME_APK_BUILT=false' >> "$GITHUB_STEP_SUMMARY"
echo 'ANDROID_DEVICE_RUNTIME_UNVERIFIED=true' >> "$GITHUB_STEP_SUMMARY"
