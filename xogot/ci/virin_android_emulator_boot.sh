#!/usr/bin/env bash
# IMPORTANT: reactivecircus android-emulator-runner executes EACH script line
# via separate '/usr/bin/sh -c'; all multi-line logic must be inside this file.
set -euo pipefail
APK=build/virin-advanced-survival/VIrin-SURVIVAL-EMULATOR-X86.apk
OUT=build/virin-advanced-survival/device-probe
PKG=com.xziel.advancedvirinsquare
mkdir -p "$OUT"
test -s "$APK"
adb install -r "$APK"
# Remove emulator-only SYSTEM MODALS (not part of the game). The prior
# screenshot-test false GREEN was a "Viewing full screen" dialog hiding a
# recording-permission dialog, not visible gameplay.
adb shell settings put secure immersive_mode_confirmations confirmed
adb shell pm grant "$PKG" android.permission.RECORD_AUDIO || true
adb logcat -c
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1
# A 3D model/animation cold boot can be slow with the emulator's software GPU.
sleep 65
adb exec-out screencap -p > "$OUT/android-screen.png"
adb logcat -d -v time > "$OUT/android-logcat.txt"
adb shell dumpsys activity top > "$OUT/foreground.txt"
if ! adb shell pidof "$PKG"; then
  echo "ANDROID_SURVIVAL_APP_EXITED_RED"
  grep -Ei 'FATAL EXCEPTION|SCRIPT ERROR|ERROR:|failed to load|could not load|vulkan' "$OUT/android-logcat.txt" | tail -n 100 || true
  exit 41
fi
python3 - "$OUT/android-screen.png" <<'PY'
import sys
from collections import Counter
from pathlib import Path
try:
    from PIL import Image
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "Pillow==11.3.0"])
    from PIL import Image
f = Path(sys.argv[1])
img = Image.open(f).convert("RGB").resize((160, 90))
pixels = list(img.getdata())
color, count = Counter(pixels).most_common(1)[0]
unique = len(set(pixels))
fraction = count / len(pixels)
print("ANDROID_REAL_SCREEN_CAPTURE", img.size, "dominant_fraction",
      round(fraction, 3), "unique_rgb", unique, "most_common", color)
# Android 35 onboarding popup has a large EXACT offwhite background;
# reject its screenshot even if there are hundreds of text antialias colors.
modal_color=(238,237,244)
modal_fraction=pixels.count(modal_color)/len(pixels)
print("ANDROID_MODAL_EXACT_COLOR_FRACTION",round(modal_fraction,4))
if modal_fraction > 0.035:
    raise SystemExit("ANDROID_UI_OVERLAY_NOT_DISMISSED_RED")
if fraction > 0.79 or unique < 28:
    raise SystemExit("ANDROID_GRAY_SCREEN_PERSISTED_RED")
print("ANDROID_SURVIVAL_VISIBLE_FRAME_GREEN")
PY
# Require ACTUAL gameplay authority, not just a running Godot process.
for marker in VIRIN_SQUARE_GEOMETRY_VISIBLE_GREEN VIRIN_SURVIVAL_SQUARE_ROUND_1_IMMEDIATE VIRIN_ORIGINAL_SURVIVAL_VIEWMODEL_GREEN XZOGOT_ZOMBIE_SPAWN; do
  if ! grep -q "$marker" "$OUT/android-logcat.txt"; then
    echo "ANDROID_GAMEPLAY_NEVER_REACHED: $marker"
    grep -Ei 'godot|SCRIPT ERROR|ERROR:|VIRIN_|XZOGOT_' "$OUT/android-logcat.txt" | tail -n 90 || true
    exit 43
  fi
done
if grep -E 'SCRIPT ERROR|Parse Error|Failed loading resource|Cannot open file' "$OUT/android-logcat.txt" \
    | grep -Ei 'Godot|virin_survival|weapon_catalog|player.gd|mobile_hud'; then
  echo "ANDROID_STARTUP_GDSCRIPT_ERROR_RED"
  exit 42
fi
echo "VIRIN_SURVIVAL_EMULATOR_VISIBLE_GAME_GREEN"
