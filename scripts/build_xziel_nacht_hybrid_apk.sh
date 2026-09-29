#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build/xziel-nacht-hybrid"
WINLATOR="$BUILD/winlator"
DIST="$BUILD/dist"
INPUT_EXE="${XZIEL_NACHT_EXE:?set XZIEL_NACHT_EXE to Nacht-Chronicles-XZIEL.exe}"

WINLATOR_COMMIT=3981d86efa4f333b2a34a7da8b6521476cd8c8b9

rm -rf "$BUILD"
mkdir -p "$BUILD" "$DIST"

test -s "$INPUT_EXE"
actual_bytes="$(wc -c < "$INPUT_EXE" | tr -d '[:space:]')"
actual_sha="$(sha256sum "$INPUT_EXE" | awk '{print $1}')"
test "$actual_bytes" -gt 800000000
test "${#actual_sha}" = "64"
if [[ -n "${XZIEL_NACHT_EXPECTED_SHA256:-}" ]]; then
    test "$actual_sha" = "$XZIEL_NACHT_EXPECTED_SHA256"
fi
echo "XZIEL_NACHT_EXE_INPUT_GREEN bytes=$actual_bytes sha256=$actual_sha"

git clone https://github.com/brunodev85/winlator-app.git "$WINLATOR"
git -C "$WINLATOR" checkout --detach "$WINLATOR_COMMIT"
test "$(git -C "$WINLATOR" rev-parse HEAD)" = "$WINLATOR_COMMIT"

python3 "$ROOT/scripts/patch_winlator_xziel_nacht_direct.py" \
    "$WINLATOR" "$actual_bytes" "$actual_sha"

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

python3 - "$APK" "$actual_bytes" "$actual_sha" <<'PY'
import hashlib, sys, zipfile
apk, expected_bytes, expected_sha = sys.argv[1], int(sys.argv[2]), sys.argv[3]
with zipfile.ZipFile(apk) as z:
    info=z.getinfo("assets/nacht-onefile.exe")
    assert info.file_size == expected_bytes, (info.file_size, expected_bytes)
    assert info.compress_type == zipfile.ZIP_STORED, info.compress_type
    h=hashlib.sha256()
    with z.open(info) as src:
        for chunk in iter(lambda: src.read(4*1024*1024), b""):
            h.update(chunk)
    actual=h.hexdigest()
    assert actual == expected_sha, (actual, expected_sha)
    print("XZIEL_APK_EMBEDDED_EXE_GREEN", {
        "bytes": info.file_size,
        "sha256": actual,
        "stored": True,
    })
PY

sha256sum "$DIST/XZIEL-Nacht-Hybrid-PixelFold-debug.apk" \
  | tee "$DIST/XZIEL-Nacht-Hybrid-PixelFold-debug.apk.sha256"
ls -lh "$DIST/XZIEL-Nacht-Hybrid-PixelFold-debug.apk"

echo "XZIEL_NACHT_HYBRID_APK_PACKAGE_GREEN"
