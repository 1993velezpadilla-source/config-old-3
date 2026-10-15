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
sleep 25
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
if grep -E 'SCRIPT ERROR|Parse Error|Failed loading resource|Cannot open file' "$OUT/android-logcat.txt" \
    | grep -Ei 'Godot|virin_survival|weapon_catalog|player.gd|mobile_hud'; then
  echo "ANDROID_STARTUP_GDSCRIPT_ERROR_RED"
  exit 42
fi
echo "VIRIN_SURVIVAL_EMULATOR_VISIBLE_GAME_GREEN"
