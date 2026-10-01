#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build"
DEPS="$BUILD/deps"
PROJECT="$BUILD/android-project"
APP="$PROJECT/app"

# Nacht golden-reference stress builds are opt-in. Normal builds remain at the
# classic 24-AI ceiling and do not enable benchmark gameplay controls.
if [[ "${XZIEL_NACHT_BENCHMARK:-0}" == "1" ]]; then
    XZIEL_MAX_AI_COUNT="${XZIEL_MAX_AI_COUNT:-96}"
else
    XZIEL_MAX_AI_COUNT="${XZIEL_MAX_AI_COUNT:-24}"
fi
export XZIEL_MAX_AI_COUNT

rm -rf "$BUILD"
mkdir -p "$DEPS"

echo "==> Cloning native dependencies"
git clone --depth 1 --branch SDL2 https://github.com/libsdl-org/SDL.git "$DEPS/SDL"
git clone --depth 1 --branch SDL2 https://github.com/libsdl-org/SDL_mixer.git "$DEPS/SDL2_mixer"
git clone --depth 1 https://github.com/ptitSeb/gl4es.git "$DEPS/gl4es"
git clone --depth 1 https://github.com/nzp-team/vril-engine.git "$DEPS/vril"
git clone --depth 1 https://github.com/nzp-team/quakec.git "$DEPS/quakec"

# Raise SDL's Android phone sensor polling target from 60 Hz to 120 Hz.
# The backend still clamps to the physical sensor's minimum delay, so devices
# that cannot sustain 120 Hz automatically run at their supported rate.
python3 - "$DEPS/SDL/src/sensor/android/SDL_androidsensor.c" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
text = text.replace("delay_us = 1000000 / 60;", "delay_us = 1000000 / 120;")
path.write_text(text)
PY

echo "==> Patching Vril for Android GLES2 through GL4ES"
python3 "$ROOT/scripts/patch_vril_android.py" "$DEPS/vril"
python3 "$ROOT/scripts/patch_vril_qc_error_log.py" "$DEPS/vril"
python3 "$ROOT/scripts/patch_vril_weaponhud.py" "$DEPS/vril"
python3 "$ROOT/scripts/patch_vril_mobile_v018.py" "$DEPS/vril"
python3 "$ROOT/scripts/patch_vril_weaponhud_v020.py" "$DEPS/vril"
python3 "$ROOT/scripts/patch_vril_combatfx.py" "$DEPS/vril"
python3 "$ROOT/scripts/patch_vril_modern_movement.py" "$DEPS/vril"
python3 "$ROOT/scripts/patch_vril_camera_feel.py" "$DEPS/vril"
python3 "$ROOT/scripts/patch_vril_animation_feel.py" "$DEPS/vril"
python3 "$ROOT/scripts/patch_vril_mobile_v021.py" "$DEPS/vril"
python3 "$ROOT/scripts/patch_vril_mobile_v022.py" "$DEPS/vril"
python3 "$ROOT/scripts/patch_vril_mobile_v024.py" "$DEPS/vril"
python3 "$ROOT/scripts/patch_vril_sanctum_staticmesh.py" "$DEPS/vril"

echo "==> Patching and compiling Xziel mobile QuakeC"
python3 -m pip install --quiet colorama==0.4.6 fastcrc==0.3.0 pandas==2.1.4 cairosvg==2.8.2
python3 "$ROOT/scripts/patch_quakec_mobile.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_combatfx.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_modern_movement.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_mobile_v021.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_mobile_v022.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_mobile_v024.py" "$DEPS/quakec"
if [[ "${XZIEL_NACHT_BENCHMARK:-0}" == "1" ]]; then
    echo "==> Enabling Nacht golden-reference stress controls"
    python3 "$ROOT/scripts/patch_quakec_nacht_benchmark.py" "$DEPS/quakec"
fi
chmod +x "$DEPS/quakec/bin/fteqcc-cli-lin" "$DEPS/quakec/tools/qc-compiler-gnu.sh"
(
    cd "$DEPS/quakec"
    bash tools/qc-compiler-gnu.sh
)

# Initialize GL4ES explicitly only after SDL has created the GLES2 context.
python3 - "$DEPS/gl4es/Android.mk" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
text = text.replace(
    "#LOCAL_CFLAGS += -DNO_INIT_CONSTRUCTOR",
    "LOCAL_CFLAGS += -DNO_INIT_CONSTRUCTOR",
)
path.write_text(text)
PY

echo "==> Creating SDL Android project"
cp -a "$DEPS/SDL/android-project" "$PROJECT"

rm -rf "$APP/jni/SDL" "$APP/jni/SDL2_mixer" "$APP/jni/gl4es" "$APP/jni/vril"
ln -s "$DEPS/SDL" "$APP/jni/SDL"
ln -s "$DEPS/SDL2_mixer" "$APP/jni/SDL2_mixer"
ln -s "$DEPS/gl4es" "$APP/jni/gl4es"
ln -s "$DEPS/vril" "$APP/jni/vril"

cp "$ROOT/android/jni/Android.mk" "$APP/jni/Android.mk"
cp "$ROOT/android/jni/Application.mk" "$APP/jni/Application.mk"
mkdir -p "$APP/jni/src"
cp "$ROOT/android/jni/src/Android.mk" "$APP/jni/src/Android.mk"
python3 - "$APP/jni/src/Android.mk" "$XZIEL_MAX_AI_COUNT" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
cap = int(sys.argv[2])
if cap < 2 or cap > 256:
    raise SystemExit(f"XZIEL_MAX_AI_COUNT out of supported benchmark range: {cap}")
text = path.read_text(encoding="utf-8")
anchor = "XZIEL_MAX_AI_COUNT ?= 24"
if anchor not in text:
    raise SystemExit("Could not find XZIEL_MAX_AI_COUNT default in generated Android.mk")
text = text.replace(anchor, f"XZIEL_MAX_AI_COUNT := {cap}", 1)
path.write_text(text, encoding="utf-8")
print(f"==> Native AI compile ceiling: {cap}")
PY

cp "$ROOT/android/app-build.gradle" "$APP/build.gradle"
cp "$ROOT/android/AndroidManifest.xml" "$APP/src/main/AndroidManifest.xml"
cp "$ROOT/android/strings.xml" "$APP/src/main/res/values/strings.xml"
cp "$ROOT/android/NZPActivity.java"    "$APP/src/main/java/org/libsdl/app/NZPActivity.java"

echo "==> Assembling official NZ:P game data for the APK"
ASSET_WORK="$BUILD/nzp-data"
DOWNLOADS="$BUILD/downloads"
mkdir -p "$ASSET_WORK" "$DOWNLOADS" "$APP/src/main/assets"

curl -fL --retry 6 --retry-delay 2 --retry-all-errors     https://github.com/nzp-team/assets/releases/download/newest/pc-nzp-assets.zip     -o "$DOWNLOADS/pc-nzp-assets.zip"

curl -fL --retry 6 --retry-delay 2 --retry-all-errors     https://github.com/nzp-team/quakec/releases/download/bleeding-edge/standard-nzp-qc.zip     -o "$DOWNLOADS/standard-nzp-qc.zip"

unzip -q "$DOWNLOADS/pc-nzp-assets.zip" -d "$ASSET_WORK"
mkdir -p "$ASSET_WORK/nzp"
unzip -q "$DOWNLOADS/standard-nzp-qc.zip" -d "$ASSET_WORK/nzp"

# Xziel mobile HUD art comes from a pinned CC0 icon pack and is rasterized at
# build time. This keeps the repository text-only while packaging professional
# touch-control art into the APK.
python3 "$ROOT/scripts/build_xziel_icons.py" "$ASSET_WORK/nzp/gfx/xziel"

# Replace the stock gameplay bytecode with our GPL QuakeC build. All other
# release-side data stays from the official NZ:P package.
cp "$DEPS/quakec/build/standard/progs.dat" "$ASSET_WORK/nzp/progs.dat"
if [[ -f "$DEPS/quakec/build/standard/progs.lno" ]]; then
    cp "$DEPS/quakec/build/standard/progs.lno" "$ASSET_WORK/nzp/progs.lno"
fi

# Optional CI/development map overlay. Normal Android builds leave these
# variables unset and are byte-for-byte unaffected by this block. Map-specific
# workflows can inject a freshly compiled BSP/NSZ without committing binary
# build outputs to the source repository.
if [[ -n "${XZIEL_EXTRA_MAP_BSP:-}" ]]; then
    test -s "$XZIEL_EXTRA_MAP_BSP"
    EXTRA_MAP_NAME="${XZIEL_EXTRA_MAP_NAME:-$(basename "$XZIEL_EXTRA_MAP_BSP" .bsp)}"
    mkdir -p "$ASSET_WORK/nzp/maps"
    cp "$XZIEL_EXTRA_MAP_BSP" "$ASSET_WORK/nzp/maps/${EXTRA_MAP_NAME}.bsp"
    echo "==> Bundled development map BSP: ${EXTRA_MAP_NAME}.bsp"

    if [[ -n "${XZIEL_EXTRA_MAP_NSZ:-}" && -s "$XZIEL_EXTRA_MAP_NSZ" ]]; then
        cp "$XZIEL_EXTRA_MAP_NSZ" "$ASSET_WORK/nzp/maps/${EXTRA_MAP_NAME}.nsz"
        echo "==> Bundled development spawn zones: ${EXTRA_MAP_NAME}.nsz"
    fi
fi

# Optional development asset overlay for map-specific visual/runtime files.
# The supplied directory is expected to mirror the NZ:P data root
# (e.g. models/... and textures/...). Normal builds leave this unset.
if [[ -n "${XZIEL_EXTRA_ASSET_DIR:-}" ]]; then
    test -d "$XZIEL_EXTRA_ASSET_DIR"
    cp -a "$XZIEL_EXTRA_ASSET_DIR"/. "$ASSET_WORK/nzp/"
    echo "==> Bundled development asset overlay: $XZIEL_EXTRA_ASSET_DIR"
fi

(
    cd "$ASSET_WORK"
    zip -q -r "$APP/src/main/assets/nzp-data.zip" .
)

sha256sum "$APP/src/main/assets/nzp-data.zip" | awk '{print $1}'     > "$APP/src/main/assets/nzp-data.version"

mkdir -p "$APP/src/main/assets/licenses"
cp "$DEPS/vril/LICENSE" "$APP/src/main/assets/licenses/VRIL-GPL-2.0.txt"
cp "$DEPS/quakec/LICENSE" "$APP/src/main/assets/licenses/NZP-QUAKEC-GPL-2.0.txt"

curl -fL --retry 6 --retry-delay 2 --retry-all-errors     https://raw.githubusercontent.com/nzp-team/assets/main/LICENSE.md     -o "$APP/src/main/assets/licenses/NZP-ASSETS-CC-BY-SA-4.0.txt"

if [[ -f "$DEPS/gl4es/LICENSE" ]]; then
    cp "$DEPS/gl4es/LICENSE" "$APP/src/main/assets/licenses/GL4ES-LICENSE.txt"
elif [[ -f "$DEPS/gl4es/LICENSE.md" ]]; then
    cp "$DEPS/gl4es/LICENSE.md" "$APP/src/main/assets/licenses/GL4ES-LICENSE.txt"
fi

echo "==> Native source revisions"
echo "SDL:        $(git -C "$DEPS/SDL" rev-parse HEAD)"
echo "SDL_mixer:  $(git -C "$DEPS/SDL2_mixer" rev-parse HEAD)"
echo "GL4ES:      $(git -C "$DEPS/gl4es" rev-parse HEAD)"
echo "Vril:       $(git -C "$DEPS/vril" rev-parse HEAD)"
echo "QuakeC:     $(git -C "$DEPS/quakec" rev-parse HEAD)"
echo "Data SHA:   $(cat "$APP/src/main/assets/nzp-data.version")"

chmod +x "$PROJECT/gradlew"

echo "Prepared project: $PROJECT"
