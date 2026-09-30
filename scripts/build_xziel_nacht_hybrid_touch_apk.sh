#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build/xziel-nacht-hybrid-touch"
WINLATOR="$BUILD/winlator"
DIST="$BUILD/dist"
RUNTIME_DIR="${XZIEL_NACHT_RUNTIME_DIR:?set XZIEL_NACHT_RUNTIME_DIR}"
VFS="${XZIEL_NACHT_VFS:?set XZIEL_NACHT_VFS}"

WINLATOR_COMMIT=3981d86efa4f333b2a34a7da8b6521476cd8c8b9

rm -rf "$BUILD"
mkdir -p "$BUILD" "$DIST"

test -d "$RUNTIME_DIR"
test -s "$RUNTIME_DIR/Xziel-Nacht.exe"
test -s "$RUNTIME_DIR/SDL2.dll"
test -s "$RUNTIME_DIR/libEGL.dll"
test -s "$RUNTIME_DIR/libGLESv2.dll"
test -s "$RUNTIME_DIR/libstdc++-6.dll"
test -s "$RUNTIME_DIR/zlib1.dll"
test -s "$VFS"

vfs_bytes="$(wc -c < "$VFS" | tr -d '[:space:]')"
vfs_sha="$(sha256sum "$VFS" | awk '{print $1}')"
runtime_sha="$(sha256sum "$RUNTIME_DIR/Xziel-Nacht.exe" | awk '{print $1}')"
if [[ "$vfs_bytes" -lt 800000000 ]]; then
  echo "VFS too small: $vfs_bytes" >&2
  exit 1
fi
if [[ "${#vfs_sha}" -ne 64 || "${#runtime_sha}" -ne 64 ]]; then
  echo "invalid direct payload sha256" >&2
  exit 1
fi
echo "XZIEL_NACHT_DIRECT_PAYLOAD_INPUT_GREEN vfs_bytes=$vfs_bytes vfs_sha256=$vfs_sha runtime_sha256=$runtime_sha"

git clone https://github.com/brunodev85/winlator-app.git "$WINLATOR"
git -C "$WINLATOR" checkout --detach "$WINLATOR_COMMIT"
test "$(git -C "$WINLATOR" rev-parse HEAD)" = "$WINLATOR_COMMIT"

python3 "$ROOT/scripts/patch_winlator_xziel_nacht_direct.py" \
  "$WINLATOR" "$vfs_bytes" "$vfs_sha" "$runtime_sha"

command -v zstd >/dev/null
python3 "$ROOT/scripts/rewrite_winlator_runtime_package.py" \
  "$WINLATOR" --old com.winlator --new com.xzielapp

ASSETS="$WINLATOR/app/src/main/assets"
HUD_SRC="$ROOT/assets/mobile/xziel_hud_v1"
HUD_DST="$ASSETS/xziel_hud"
mkdir -p "$HUD_DST"

hud_count=0
for src in "$HUD_SRC"/*.webp.b64; do
  test -s "$src"
  name="$(basename "$src" .b64)"
  base64 -d "$src" > "$HUD_DST/$name"
  test -s "$HUD_DST/$name"
  magic="$(head -c 4 "$HUD_DST/$name")"
  test "$magic" = "RIFF"
  hud_count=$((hud_count + 1))
done
test "$hud_count" = "12"
echo "XZIEL_HUD_ZOMBIES_MOBILE_V1_ASSETS_GREEN count=$hud_count"

RUNTIME_ASSETS="$ASSETS/nacht-runtime"
mkdir -p "$RUNTIME_ASSETS"
cp "$RUNTIME_DIR"/*.exe "$RUNTIME_ASSETS/"
cp "$RUNTIME_DIR"/*.dll "$RUNTIME_ASSETS/"
cp "$VFS" "$ASSETS/nacht-vfs.zip"

test -s "$RUNTIME_ASSETS/Xziel-Nacht.exe"
test -s "$RUNTIME_ASSETS/SDL2.dll"
test -s "$RUNTIME_ASSETS/libEGL.dll"
test -s "$RUNTIME_ASSETS/libGLESv2.dll"
test -s "$RUNTIME_ASSETS/libstdc++-6.dll"
test -s "$RUNTIME_ASSETS/zlib1.dll"
test -s "$ASSETS/nacht-vfs.zip"
echo "XZIEL_DIRECT_PAYLOAD_ASSETS_GREEN"

cd "$WINLATOR"
chmod +x gradlew

export GRADLE_USER_HOME="$BUILD/gradle-home"
mkdir -p "$GRADLE_USER_HOME"
cat > "$GRADLE_USER_HOME/gradle.properties" <<'GRADLE'
org.gradle.jvmargs=-Xmx6g -XX:MaxMetaspaceSize=1024m -Dfile.encoding=UTF-8
org.gradle.parallel=false
org.gradle.daemon=false
android.nonFinalResIds=false
android.nonTransitiveRClass=false
GRADLE
unset GRADLE_OPTS || true
unset JAVA_OPTS || true

./gradlew --no-daemon --stacktrace   -Pandroid.nonFinalResIds=false   -Pandroid.nonTransitiveRClass=false   :app:assembleDebug

APK="$WINLATOR/app/build/outputs/apk/debug/app-debug.apk"
test -s "$APK"
cp "$APK" "$DIST/XZIEL-Nacht-Hybrid-TouchGyro-PixelFold-debug.apk"

unzip -l "$APK" > "$DIST/apk-contents.txt"
grep -q 'assets/rootfs.tzst' "$DIST/apk-contents.txt"
grep -q 'assets/container_pattern.tzst' "$DIST/apk-contents.txt"
grep -q 'assets/nacht-vfs.zip' "$DIST/apk-contents.txt"
grep -q 'assets/nacht-runtime/Xziel-Nacht.exe' "$DIST/apk-contents.txt"
grep -q 'assets/nacht-runtime/SDL2.dll' "$DIST/apk-contents.txt"
grep -q 'assets/nacht-runtime/libEGL.dll' "$DIST/apk-contents.txt"
grep -q 'assets/nacht-runtime/libGLESv2.dll' "$DIST/apk-contents.txt"
grep -q 'assets/licenses/WINLATOR-LGPL-2.1.txt' "$DIST/apk-contents.txt"
grep -q 'assets/xziel_hud/hud_fire.webp' "$DIST/apk-contents.txt"
grep -q 'assets/xziel_hud/hud_ads.webp' "$DIST/apk-contents.txt"
grep -q 'assets/xziel_hud/hud_ads_fire.webp' "$DIST/apk-contents.txt"
grep -q 'assets/xziel_hud/hud_reload.webp' "$DIST/apk-contents.txt"
grep -q 'assets/xziel_hud/hud_crouch.webp' "$DIST/apk-contents.txt"
grep -q 'assets/xziel_hud/hud_prone.webp' "$DIST/apk-contents.txt"
grep -q 'assets/xziel_hud/hud_slide.webp' "$DIST/apk-contents.txt"
grep -q 'assets/xziel_hud/hud_sprint.webp' "$DIST/apk-contents.txt"
grep -q 'assets/xziel_hud/hud_grenade.webp' "$DIST/apk-contents.txt"
grep -q 'assets/xziel_hud/hud_swap.webp' "$DIST/apk-contents.txt"
grep -q 'assets/xziel_hud/hud_knife.webp' "$DIST/apk-contents.txt"
grep -q 'assets/xziel_hud/hud_claw.webp' "$DIST/apk-contents.txt"
grep -q 'lib/arm64-v8a/' "$DIST/apk-contents.txt"

python3 - "$APK" "$vfs_bytes" "$runtime_sha" <<'PY'
import hashlib, sys, zipfile
apk=sys.argv[1]
expected_vfs=int(sys.argv[2])
expected_runtime_sha=sys.argv[3]
with zipfile.ZipFile(apk) as z:
    vfs=z.getinfo("assets/nacht-vfs.zip")
    assert vfs.file_size == expected_vfs, (vfs.file_size, expected_vfs)
    assert vfs.compress_type == zipfile.ZIP_STORED, vfs.compress_type
    runtime=z.read("assets/nacht-runtime/Xziel-Nacht.exe")
    assert hashlib.sha256(runtime).hexdigest() == expected_runtime_sha
    names=set(z.namelist())
    assert "assets/licenses/XZIEL-HYBRID-NOTICE.txt" in names
    print("XZIEL_APK_DIRECT_PAYLOAD_GREEN", {
        "vfs_bytes": vfs.file_size,
        "runtime_bytes": len(runtime),
        "vfs_stored": True,
    })
PY

# Verify the patched classes and direct-boot contract made it into source before APK packaging.
test -s "$WINLATOR/app/src/main/java/com/winlator/XzielMobileOverlay.java"
grep -q 'GYRO_NORMAL_PX_PER_RAD' "$WINLATOR/app/src/main/java/com/winlator/XzielMobileOverlay.java"
grep -q 'ROLE_ADSFIRE' "$WINLATOR/app/src/main/java/com/winlator/XzielMobileOverlay.java"
grep -q 'xziel_direct_boot' "$WINLATOR/app/src/main/java/com/winlator/XServerDisplayActivity.java"
grep -q 'com.winlator.XzielBootActivity' "$WINLATOR/app/src/main/AndroidManifest.xml"

sha256sum "$DIST/XZIEL-Nacht-Hybrid-TouchGyro-PixelFold-debug.apk"   | tee "$DIST/XZIEL-Nacht-Hybrid-TouchGyro-PixelFold-debug.apk.sha256"

cat > "$DIST/control-contract.txt" <<EOF
XZIEL_TOUCH_GYRO_CONTRACT
payload_mode=direct_runtime_vfs
source_vfs_bytes=$vfs_bytes
source_vfs_sha256=$vfs_sha
runtime_exe_sha256=$runtime_sha
launch_exe=Xziel-Nacht.exe
launch_args=--xziel-root C:\\XZIEL --xziel-map xziel_nacht_bo3
nsis_wrapper=bypassed
joystick=WASD
look=raw_mouse_delta
gyro=enabled
gyro_general_px_per_rad=920
gyro_ads_scope_px_per_rad=520
hip_fire=mouse_left
ads=mouse_right
ads_fire=mouse_right+mouse_left
reload=R
interact=E
crouch=CTRL
sprint=SHIFT
grenade=G
swap=Q
jump=SPACE
knife=F
pause=ESC
skin=xziel_hud_zombies_mobile_v1
skin_asset_count=12
skin_idle_alpha=210
skin_pressed_alpha=246
prone=C
slide=CTRL
winlator_ui=hidden
application_id=com.xzielapp
runtime_package_paths_rewritten=1
EOF

ls -lh "$DIST/XZIEL-Nacht-Hybrid-TouchGyro-PixelFold-debug.apk"
echo "XZIEL_NACHT_HYBRID_TOUCH_GYRO_APK_GREEN"
