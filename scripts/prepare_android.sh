#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build"
DEPS="$BUILD/deps"
PROJECT="$BUILD/android-project"
APP="$PROJECT/app"

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
python3 "$ROOT/scripts/patch_vril_xz_phase0.py" "$DEPS/vril"
python3 "$ROOT/scripts/patch_vril_xziel_strict_assets.py" "$DEPS/vril"

echo "==> Patching and compiling Xziel mobile QuakeC"
python3 -m pip install --quiet colorama==0.4.6 fastcrc==0.3.0 pandas==2.1.4 cairosvg==2.8.2
python3 "$ROOT/scripts/patch_quakec_mobile.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_combatfx.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_modern_movement.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_mobile_v021.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_mobile_v022.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_mobile_v024.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_xziel_burst_timing.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_xziel_damage_falloff.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_xziel_weapon_registry.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_xziel_pack_a_punch_identity.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_xziel_mystery_box_capacity.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_xziel_zombies_runtime_bridge.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_xziel_gobblegum_pap_events.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_xziel_death_machine_state.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_xziel_gobblegum_ephemeral.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_xziel_gobblegum_disorderly.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_xziel_gobblegum_disorderly_runtime.py" "$DEPS/quakec"
python3 "$ROOT/scripts/patch_quakec_xziel_rk5_logic.py" "$DEPS/quakec"
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

cp "$ROOT/android/app-build.gradle" "$APP/build.gradle"
cp "$ROOT/android/AndroidManifest.xml" "$APP/src/main/AndroidManifest.xml"
cp "$ROOT/android/strings.xml" "$APP/src/main/res/values/strings.xml"
cp "$ROOT/android/NZPActivity.java"    "$APP/src/main/java/org/libsdl/app/NZPActivity.java"
cp "$ROOT/android/XzielMapPackageInstaller.java" \
    "$APP/src/main/java/org/libsdl/app/XzielMapPackageInstaller.java"

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

# Bundle the global XZIEL weapon identity catalog and generated Mystery Box pool.
# These are gameplay metadata only; native weapon implementations/assets remain separate.
mkdir -p "$ASSET_WORK/nzp/xziel/weapons"
cp "$ROOT/assets/weapons/xziel_weapon_catalog_v1.json" \
    "$ASSET_WORK/nzp/xziel/weapons/xziel_weapon_catalog_v1.json"
cp "$ROOT/assets/weapons/xziel_mystery_box_pool_v1.json" \
    "$ASSET_WORK/nzp/xziel/weapons/xziel_mystery_box_pool_v1.json"
cp "$ROOT/assets/weapons/xziel_weapon_id_registry_v1.json" \
    "$ASSET_WORK/nzp/xziel/weapons/xziel_weapon_id_registry_v1.json"
cp "$ROOT/assets/weapons/xziel_mystery_box_runtime_pool_v1.json" \
    "$ASSET_WORK/nzp/xziel/weapons/xziel_mystery_box_runtime_pool_v1.json"

cp "$ROOT/assets/weapons/nacht_prototype_box_pool_v1.json" \
    "$ASSET_WORK/nzp/xziel/weapons/nacht_prototype_box_pool_v1.json"

# Optional CI/development map overlay. The normal product build remains
# unchanged when these variables are unset. Map-specific workflows can inject
# freshly compiled BSP/NSZ files without committing generated binaries.
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

    if [[ -n "${XZIEL_EXTRA_MAP_MB2:-}" && -s "$XZIEL_EXTRA_MAP_MB2" ]]; then
        cp "$XZIEL_EXTRA_MAP_MB2" "$ASSET_WORK/nzp/maps/${EXTRA_MAP_NAME}.mb2"
        echo "==> Bundled readiness-gated Mystery Box pool: ${EXTRA_MAP_NAME}.mb2"
    fi
fi

# Optional static-scene visual harness. This deliberately reuses only a
# known-good Quake BSP for camera/spawn/input while giving the world model the
# target XZIEL map id. XzStaticSceneRuntime then resolves the visible world from
# xziel/maps/<map-id>/scene.xzsc and its native XZMS/XZMI/XZML/XZTX payload.
# No target-map geometry, materials or textures come from the harness BSP.
if [[ -n "${XZIEL_STATIC_SCENE_MAP_ID:-}" ]]; then
    STATIC_SCENE_MAP_ID="${XZIEL_STATIC_SCENE_MAP_ID}"
    STATIC_SCENE_HARNESS_MAP="${XZIEL_STATIC_SCENE_HARNESS_MAP:-ndu}"

    if [[ ! "$STATIC_SCENE_MAP_ID" =~ ^[a-z0-9][a-z0-9_]{0,62}$ ]]; then
        echo "Invalid XZIEL_STATIC_SCENE_MAP_ID: $STATIC_SCENE_MAP_ID" >&2
        exit 1
    fi
    if [[ ! "$STATIC_SCENE_HARNESS_MAP" =~ ^[A-Za-z0-9_][A-Za-z0-9_-]{0,62}$ ]]; then
        echo "Invalid XZIEL_STATIC_SCENE_HARNESS_MAP: $STATIC_SCENE_HARNESS_MAP" >&2
        exit 1
    fi

    HARNESS_BSP="$ASSET_WORK/nzp/maps/${STATIC_SCENE_HARNESS_MAP}.bsp"
    TARGET_BSP="$ASSET_WORK/nzp/maps/${STATIC_SCENE_MAP_ID}.bsp"
    test -s "$HARNESS_BSP"
    cp "$HARNESS_BSP" "$TARGET_BSP"

    # Preserve optional engine-side companions when the source map provides
    # them. These are harness-only and never replace XZIEL native scene data.
    for ext in lit ent vis nsz; do
        if [[ -s "$ASSET_WORK/nzp/maps/${STATIC_SCENE_HARNESS_MAP}.${ext}" ]]; then
            cp "$ASSET_WORK/nzp/maps/${STATIC_SCENE_HARNESS_MAP}.${ext}"                "$ASSET_WORK/nzp/maps/${STATIC_SCENE_MAP_ID}.${ext}"
        fi
    done

    echo "==> Bundled static-scene harness: ${STATIC_SCENE_MAP_ID}.bsp <- ${STATIC_SCENE_HARNESS_MAP}.bsp"
fi

# Optional transformed/owned visual asset overlay (models, textures, etc.).
# The directory mirrors the NZ:P data root and is only included when supplied.
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
