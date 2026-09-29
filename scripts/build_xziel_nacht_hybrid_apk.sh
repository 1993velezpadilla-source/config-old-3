#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build/xziel-nacht-hybrid"
WINLATOR="$BUILD/winlator"
DIST="$BUILD/dist"
INPUT_EXE="${XZIEL_NACHT_EXE:?set XZIEL_NACHT_EXE to Nacht-Chronicles-XZIEL.exe}"

EXPECTED_BYTES=887735046
EXPECTED_SHA256=2cc8876fc79d50c3731f8f0681e3bfeb2e2cef084b87bf1b8a87c8c43a430d02
WINLATOR_COMMIT=3981d86efa4f333b2a34a7da8b6521476cd8c8b9

rm -rf "$BUILD"
mkdir -p "$BUILD" "$DIST"

test -s "$INPUT_EXE"
actual_bytes="$(wc -c < "$INPUT_EXE" | tr -d '[:space:]')"
test "$actual_bytes" = "$EXPECTED_BYTES"
actual_sha="$(sha256sum "$INPUT_EXE" | awk '{print $1}')"
test "$actual_sha" = "$EXPECTED_SHA256"
echo "XZIEL_NACHT_EXE_INPUT_GREEN bytes=$actual_bytes sha256=$actual_sha"

git clone https://github.com/brunodev85/winlator-app.git "$WINLATOR"
git -C "$WINLATOR" checkout --detach "$WINLATOR_COMMIT"
test "$(git -C "$WINLATOR" rev-parse HEAD)" = "$WINLATOR_COMMIT"

python3 "$ROOT/scripts/patch_winlator_xziel_nacht_direct.py" "$WINLATOR"

ASSETS="$WINLATOR/app/src/main/assets"
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

./gradlew --no-daemon --stacktrace \
  -Pandroid.nonFinalResIds=false \
  -Pandroid.nonTransitiveRClass=false \
  :app:assembleDebug

APK="$WINLATOR/app/build/outputs/apk/debug/app-debug.apk"
test -s "$APK"
cp "$APK" "$DIST/XZIEL-Nacht-Hybrid-PixelFold-debug.apk"

unzip -l "$APK" > "$DIST/apk-contents.txt"
grep -q 'assets/rootfs.tzst' "$DIST/apk-contents.txt"
grep -q 'assets/container_pattern.tzst' "$DIST/apk-contents.txt"
grep -q 'assets/nacht-onefile.exe' "$DIST/apk-contents.txt"
grep -q 'assets/licenses/WINLATOR-LGPL-2.1.txt' "$DIST/apk-contents.txt"
grep -q 'lib/arm64-v8a/' "$DIST/apk-contents.txt"

python3 - "$APK" <<'PY'
import sys, zipfile
apk=sys.argv[1]
with zipfile.ZipFile(apk) as z:
    info=z.getinfo("assets/nacht-onefile.exe")
    assert info.file_size == 887735046, info.file_size
    assert info.compress_type == zipfile.ZIP_STORED, info.compress_type
    print("XZIEL_APK_EMBEDDED_EXE_GREEN", {
        "bytes": info.file_size,
        "stored": True,
    })
PY

sha256sum "$DIST/XZIEL-Nacht-Hybrid-PixelFold-debug.apk" \
  | tee "$DIST/XZIEL-Nacht-Hybrid-PixelFold-debug.apk.sha256"
ls -lh "$DIST/XZIEL-Nacht-Hybrid-PixelFold-debug.apk"

echo "XZIEL_NACHT_HYBRID_APK_PACKAGE_GREEN"
