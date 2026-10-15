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
adb logcat -c
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1
# Android API35 immersive-mode safety dialog covers the entire 3D screen
# on the first install. Dismiss it like a normal player would.
sleep 8
adb shell input tap 1315 385
adb shell input keyevent KEYCODE_ENTER || true
# Large source animations take time on SwiftShader CPU Vulkan; do NOT capture
# a splash/permission screen instead of actual Godot gameplay.
sleep 48
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
