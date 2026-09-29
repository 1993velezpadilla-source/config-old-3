#!/usr/bin/env bash
# CI probe for the direct-boot XZIEL hybrid APK.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build/xziel-hybrid"
WINLATOR="$BUILD/winlator"
DIST="$BUILD/dist"

rm -rf "$BUILD"
mkdir -p "$BUILD" "$DIST"

echo "==> Building XZIEL Windows x64 guest"
XZIEL_NACHT_BENCHMARK=1 XZIEL_MAX_AI_COUNT=96 \
    bash "$ROOT/scripts/prepare_windows_x64.sh"

GAME_DIR="$ROOT/build/xziel-win64/dist/XZIEL-WIN64"
test -s "$GAME_DIR/Xziel.exe"
test -s "$GAME_DIR/nzp/progs.dat"

echo "==> Cloning Winlator compatibility layer"
git clone --depth 1 https://github.com/brunodev85/winlator-app.git "$WINLATOR"

echo "==> Applying XZIEL direct-boot patch"
python3 "$ROOT/scripts/patch_winlator_xziel_direct.py" "$WINLATOR"

echo "==> Embedding XZIEL game package inside APK"
ASSETS="$WINLATOR/app/src/main/assets"
rm -f "$ASSETS/xziel-game.zip"
(
    cd "$GAME_DIR"
    zip -q -r "$ASSETS/xziel-game.zip" .
)

test -s "$ASSETS/xziel-game.zip"
echo "Guest payload: $(du -h "$ASSETS/xziel-game.zip" | awk '{print $1}')"

echo "==> Building XZIEL hybrid APK"
cd "$WINLATOR"
chmod +x gradlew

# GitHub-hosted runners may carry a user-level Gradle configuration from
# unrelated Android jobs. Isolate this build so only valid JVM options reach
# the daemon.
export GRADLE_USER_HOME="$BUILD/gradle-home"
mkdir -p "$GRADLE_USER_HOME"
cat > "$GRADLE_USER_HOME/gradle.properties" <<'GRADLE'
org.gradle.jvmargs=-Xmx4g -XX:MaxMetaspaceSize=1024m -Dfile.encoding=UTF-8
org.gradle.parallel=false
org.gradle.daemon=false
android.nonFinalResIds=false
android.nonTransitiveRClass=false
GRADLE
unset GRADLE_OPTS || true
unset JAVA_OPTS || true
./gradlew --no-daemon --stacktrace -Pandroid.nonFinalResIds=false -Pandroid.nonTransitiveRClass=false :app:assembleDebug

APK="$WINLATOR/app/build/outputs/apk/debug/app-debug.apk"
test -s "$APK"
cp "$APK" "$DIST/XZIEL-Hybrid-PixelFold-debug.apk"

echo "==> Verifying embedded runtime contract"
unzip -l "$APK" > "$DIST/apk-contents.txt"
grep -q 'assets/rootfs.tzst' "$DIST/apk-contents.txt"
grep -q 'assets/container_pattern.tzst' "$DIST/apk-contents.txt"
grep -q 'assets/xziel-game.zip' "$DIST/apk-contents.txt"
grep -q 'assets/licenses/WINLATOR-LGPL-2.1.txt' "$DIST/apk-contents.txt"
grep -q 'lib/arm64-v8a/' "$DIST/apk-contents.txt"

sha256sum "$DIST/XZIEL-Hybrid-PixelFold-debug.apk" | tee "$DIST/XZIEL-Hybrid-PixelFold-debug.apk.sha256"
ls -lh "$DIST/XZIEL-Hybrid-PixelFold-debug.apk"

echo "XZIEL_HYBRID_APK_PACKAGE_OK"
echo "APK: $DIST/XZIEL-Hybrid-PixelFold-debug.apk"
