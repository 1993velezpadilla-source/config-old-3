#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build/xziel-nacht-direct-payload"
WINLATOR="$BUILD/winlator"
DIST="$BUILD/dist"
VFS="${XZIEL_NACHT_VFS:?set XZIEL_NACHT_VFS}"
RUNTIME_DIR="${XZIEL_NACHT_RUNTIME_DIR:?set XZIEL_NACHT_RUNTIME_DIR}"
WINLATOR_COMMIT=3981d86efa4f333b2a34a7da8b6521476cd8c8b9

rm -rf "$BUILD"
mkdir -p "$BUILD" "$DIST"

test -s "$VFS"
test -s "$RUNTIME_DIR/Xziel-Nacht.exe"
for dll in SDL2.dll libEGL.dll libGLESv2.dll libstdc++-6.dll zlib1.dll; do
  test -s "$RUNTIME_DIR/$dll"
done

vfs_bytes="$(wc -c < "$VFS" | tr -d '[:space:]')"
vfs_sha="$(sha256sum "$VFS" | awk '{print $1}')"
test "$vfs_bytes" -gt 800000000
test "${#vfs_sha}" = "64"

unzip -l "$VFS" | grep -q 'xziel/maps/xziel_nacht_bo3/scene.xzsc'
mesh_count="$(unzip -Z1 "$VFS" | grep -E '^xziel/maps/xziel_nacht_bo3/meshes/[^/]+[.]xzm$' | wc -l | tr -d '[:space:]')"
test "$mesh_count" = "492"
echo "XZIEL_DIRECT_VFS_GREEN bytes=$vfs_bytes meshes=$mesh_count sha256=$vfs_sha"

RUNTIME_ZIP="$BUILD/xziel-runtime.zip"
python3 - "$RUNTIME_DIR" "$RUNTIME_ZIP" <<'PY'
from pathlib import Path
import sys, zipfile
src=Path(sys.argv[1])
dst=Path(sys.argv[2])
files=[p for p in src.rglob("*") if p.is_file()]
if not files:
    raise SystemExit("runtime dir empty")
with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
    for p in sorted(files):
        z.write(p, p.relative_to(src).as_posix())
print("XZIEL_DIRECT_RUNTIME_ZIP_GREEN", len(files), dst.stat().st_size)
PY
runtime_sha="$(sha256sum "$RUNTIME_ZIP" | awk '{print $1}')"
test "${#runtime_sha}" = "64"

git clone https://github.com/brunodev85/winlator-app.git "$WINLATOR"
git -C "$WINLATOR" checkout --detach "$WINLATOR_COMMIT"
test "$(git -C "$WINLATOR" rev-parse HEAD)" = "$WINLATOR_COMMIT"

python3 "$ROOT/scripts/patch_winlator_xziel_nacht_direct.py"   "$WINLATOR" "$vfs_bytes" "$vfs_sha"
python3 "$ROOT/scripts/patch_winlator_xziel_nacht_direct_payload.py"   "$WINLATOR" "$runtime_sha" "$vfs_sha"

python3 "$ROOT/scripts/rewrite_winlator_runtime_package.py"   "$WINLATOR" --old com.winlator --new com.xzielapp

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
  test "$(head -c 4 "$HUD_DST/$name")" = "RIFF"
  hud_count=$((hud_count + 1))
done
test "$hud_count" = "12"

cp "$VFS" "$ASSETS/xziel-nacht-vfs.zip"
cp "$RUNTIME_ZIP" "$ASSETS/xziel-runtime.zip"
test -s "$ASSETS/xziel-nacht-vfs.zip"
test -s "$ASSETS/xziel-runtime.zip"

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
OUT_APK="$DIST/XZIEL-Nacht-DirectPayload-PixelFold-debug.apk"
cp "$APK" "$OUT_APK"

unzip -l "$APK" > "$DIST/apk-contents.txt"
grep -q 'assets/rootfs.tzst' "$DIST/apk-contents.txt"
grep -q 'assets/container_pattern.tzst' "$DIST/apk-contents.txt"
grep -q 'assets/xziel-nacht-vfs.zip' "$DIST/apk-contents.txt"
grep -q 'assets/xziel-runtime.zip' "$DIST/apk-contents.txt"
grep -q 'assets/xziel_hud/hud_fire.webp' "$DIST/apk-contents.txt"
grep -q 'lib/arm64-v8a/' "$DIST/apk-contents.txt"

python3 - "$APK" "$vfs_bytes" <<'PY'
import sys, zipfile
apk=sys.argv[1]
expected=int(sys.argv[2])
with zipfile.ZipFile(apk) as z:
    v=z.getinfo("assets/xziel-nacht-vfs.zip")
    r=z.getinfo("assets/xziel-runtime.zip")
    assert v.file_size == expected, (v.file_size, expected)
    assert v.compress_type == zipfile.ZIP_STORED, v.compress_type
    assert r.compress_type == zipfile.ZIP_STORED, r.compress_type
    print("XZIEL_DIRECT_APK_ASSETS_GREEN", {
        "vfs_bytes": v.file_size,
        "runtime_bytes": r.file_size,
        "stored": True,
    })
PY

grep -q 'Xziel-Nacht.exe --xziel-root'   "$WINLATOR/app/src/main/java/com/winlator/XServerDisplayActivity.java"
grep -q 'DIRECT_PAYLOAD_INSTALL_GREEN'   "$WINLATOR/app/src/main/java/com/winlator/XzielBootActivity.java"
grep -q 'guestExecutable.contains("Xziel-Nacht.exe")'   "$WINLATOR/app/src/main/java/com/winlator/xenvironment/components/GuestProgramLauncherComponent.java"

sha256sum "$OUT_APK" | tee "$DIST/XZIEL-Nacht-DirectPayload-PixelFold-debug.apk.sha256"
cat > "$DIST/direct-payload-contract.txt" <<EOF
XZIEL_NACHT_DIRECT_PAYLOAD_ANDROID
runtime_source_run=36644605239
vfs_source_run=36642428359
vfs_bytes=$vfs_bytes
vfs_sha256=$vfs_sha
runtime_zip_sha256=$runtime_sha
mesh_count=$mesh_count
launch=wine C:\\XZIEL\\Xziel-Nacht.exe --xziel-root C:\\XZIEL --xziel-map xziel_nacht_bo3
nsis_runtime_boot=disabled
hud_skin_count=12
EOF

echo "XZIEL_NACHT_DIRECT_PAYLOAD_APK_GREEN apk=$OUT_APK"
