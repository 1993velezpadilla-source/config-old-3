#!/usr/bin/env bash
# Reproduce and vendor the ORIGINAL XZIEL/Vril NZ:P Android v0.26 sources.
# This is only a source snapshot, NOT an IW3 merge or a gameplay modification.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/third_party/viril-iw3-v026"
TMP="$(mktemp -d "${RUNNER_TEMP:-/tmp}/viril-iw3-v026.XXXXXXXX")"
trap 'rm -rf "$TMP"' EXIT

if [[ -e "$DEST/vril/source/view.c" || -e "$DEST/quakec/source/shared/weapon_stats.qc" ]]; then
  echo "Source snapshot already present; refusing to overwrite without an explicit review."
  exit 1
fi

clone_pin() {
  local name="$1" url="$2" revision="$3" branch="${4:-}"
  if [[ -n "$branch" ]]; then
    git clone -q --depth 1 --branch "$branch" "$url" "$TMP/$name"
  else
    git clone -q --depth 1 "$url" "$TMP/$name"
  fi
  git -C "$TMP/$name" fetch -q --depth 1 origin "$revision"
  git -C "$TMP/$name" checkout -q --detach "$revision"
  local actual
  actual="$(git -C "$TMP/$name" rev-parse HEAD)"
  [[ "$actual" == "$revision" ]] || { echo "PIN MISMATCH: $name" >&2; exit 1; }
  echo "Pinned $name at $actual"
}

clone_pin vril "https://github.com/nzp-team/vril-engine.git" "aaa474061bff5d0e3aa471ac01f5f0e01b4fca31"
clone_pin quakec "https://github.com/nzp-team/quakec.git" "8a77f1ce45f1a2b9aa0afb301446954fda40e696"
clone_pin SDL "https://github.com/libsdl-org/SDL.git" "b90ac95029d801c5abc59472ba8e2200dff31e1e" SDL2
clone_pin SDL2_mixer "https://github.com/libsdl-org/SDL_mixer.git" "34370d92840d5aa32b4369dc56c6735ef7adf1a8" SDL2
clone_pin gl4es "https://github.com/ptitSeb/gl4es.git" "81547d986798e876de8b434193920b606a72363f"

# Mirror the source-altering SDL Android change in the original v0.26 recipe.
python3 - "$TMP/SDL/src/sensor/android/SDL_androidsensor.c" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text(encoding="utf-8")
old="delay_us = 1000000 / 60;"
new="delay_us = 1000000 / 120;"
assert old in s or new in s, "SDL v0.26 sensor anchor missing"
p.write_text(s.replace(old,new),encoding="utf-8")
PY

# Run the original v0.26 patch chain without modifying the original project.
for patch in \
  patch_vril_android.py \
  patch_vril_weaponhud.py \
  patch_vril_mobile_v018.py \
  patch_vril_weaponhud_v020.py \
  patch_vril_combatfx.py \
  patch_vril_modern_movement.py \
  patch_vril_camera_feel.py \
  patch_vril_animation_feel.py \
  patch_vril_mobile_v021.py \
  patch_vril_mobile_v022.py \
  patch_vril_mobile_v024.py \
  patch_vril_multiplayer_hud_test.py \
  patch_vril_multiplayer_online.py \
  patch_vril_sanctum_staticmesh.py \
  patch_vril_official_touch_skins_v026.py; do
  echo "Applying Vril: $patch"
  python3 "$ROOT/scripts/$patch" "$TMP/vril"
done

for patch in \
  patch_quakec_mobile.py \
  patch_quakec_combatfx.py \
  patch_quakec_modern_movement.py \
  patch_quakec_mobile_v021.py \
  patch_quakec_mobile_v022.py \
  patch_quakec_mobile_v024.py \
  patch_quakec_multiplayer_v026.py; do
  echo "Applying QuakeC: $patch"
  python3 "$ROOT/scripts/$patch" "$TMP/quakec"
done

# Mirror the source-altering GL4ES build flag in the original v0.26 recipe.
python3 - "$TMP/gl4es/Android.mk" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text(encoding="utf-8")
old="#LOCAL_CFLAGS += -DNO_INIT_CONSTRUCTOR"
new="LOCAL_CFLAGS += -DNO_INIT_CONSTRUCTOR"
assert old in s or new in s, "GL4ES v0.26 Android.mk anchor missing"
p.write_text(s.replace(old,new),encoding="utf-8")
PY

mkdir -p "$DEST"
for name in vril quakec SDL SDL2_mixer gl4es; do
  mkdir -p "$DEST/$name"
  rsync -a --exclude='/.git/' "$TMP/$name/" "$DEST/$name/"
done

# Verify that both the native engine and the actual QuakeC weapon definitions
# are included, and that the stock v0.26 weapon handling was retained.
test -s "$DEST/vril/source/view.c"
test -s "$DEST/quakec/source/shared/weapon_stats.qc"
test -s "$DEST/quakec/source/client/view_model.qc"
grep -q 'GetWeaponADSOfs' "$DEST/quakec/source/shared/weapon_stats.qc"
grep -q 'case W_MP40:' "$DEST/quakec/source/shared/weapon_stats.qc"
grep -q 'Xziel_AddVisualWeaponRecoil' "$DEST/vril/source/view.c"
grep -q 'xziel' "$DEST/vril/source/view.c"

cat > "$DEST/SOURCE_MANIFEST.md" <<'EOF'
# Viril IW3 — complete v0.26 source snapshot (not an IW3 integration)

Exact pins from the working original XZIEL NZ:P Android v0.26 recovery:
- Vril: nzp-team/vril-engine @ aaa474061bff5d0e3aa471ac01f5f0e01b4fca31
- QuakeC: nzp-team/quakec @ 8a77f1ce45f1a2b9aa0afb301446954fda40e696
- SDL/SDL2: libsdl-org/SDL @ b90ac95029d801c5abc59472ba8e2200dff31e1e
- SDL2_mixer: libsdl-org/SDL_mixer @ 34370d92840d5aa32b4369dc56c6735ef7adf1a8
- GL4ES: ptitSeb/gl4es @ 81547d986798e876de8b434193920b606a72363f

Each tree contains the **full files** of the pinned upstream revision, plus
the original XZIEL v0.26 source-altering patch sequence as applied by
`scripts/prepare_android.sh`. Original upstream license files are retained.
`.git` object directories are deliberately not duplicated.

No IW3 code was added here; this commit is a stable backup/source baseline.
Art, maps, extracted commercial-game data, and APK output are not included.
EOF

for name in vril quakec SDL SDL2_mixer gl4es; do
  echo "Source files ($name): $(find "$DEST/$name" -type f | wc -l)"
done
echo "Complete v0.26 source snapshot prepared: $DEST"
