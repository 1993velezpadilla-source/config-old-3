#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build/xziel-nacht-hybrid-touch"
WINLATOR="$BUILD/winlator"
DIST="$BUILD/dist"
INPUT_EXE="${XZIEL_NACHT_EXE:?set XZIEL_NACHT_EXE}"

WINLATOR_COMMIT=3981d86efa4f333b2a34a7da8b6521476cd8c8b9

rm -rf "$BUILD"
mkdir -p "$BUILD" "$DIST"

test -s "$INPUT_EXE"
actual_bytes="$(wc -c < "$INPUT_EXE" | tr -d '[:space:]')"
actual_sha="$(sha256sum "$INPUT_EXE" | awk '{print $1}')"
if [[ "$actual_bytes" -lt 800000000 ]]; then
  echo "EXE too small: $actual_bytes" >&2
  exit 1
fi
if [[ "${#actual_sha}" -ne 64 ]]; then
  echo "invalid sha256" >&2
  exit 1
fi
echo "XZIEL_NACHT_EXE_INPUT_GREEN bytes=$actual_bytes sha256=$actual_sha"

git clone https://github.com/brunodev85/winlator-app.git "$WINLATOR"
git -C "$WINLATOR" checkout --detach "$WINLATOR_COMMIT"
test "$(git -C "$WINLATOR" rev-parse HEAD)" = "$WINLATOR_COMMIT"

python3 "$ROOT/scripts/patch_winlator_xziel_nacht_direct.py" \
  "$WINLATOR" "$actual_bytes" "$actual_sha"

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

cp "$INPUT_EXE" "$ASSETS/nacht-onefile.exe"
test -s "$ASSETS/nacht-onefile.exe"

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
grep -q 'assets/nacht-onefile.exe' "$DIST/apk-contents.txt"
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

python3 - "$APK" "$actual_bytes" <<'PY'
import sys, zipfile
apk=sys.argv[1]
expected=int(sys.argv[2])
with zipfile.ZipFile(apk) as z:
    info=z.getinfo("assets/nacht-onefile.exe")
    assert info.file_size == expected, (info.file_size, expected)
    assert info.compress_type == zipfile.ZIP_STORED, info.compress_type
    names=set(z.namelist())
    assert "assets/licenses/XZIEL-HYBRID-NOTICE.txt" in names
    print("XZIEL_APK_EMBEDDED_EXE_GREEN", {"bytes": info.file_size, "stored": True})
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
source_exe_bytes=$actual_bytes
source_exe_sha256=$actual_sha
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
