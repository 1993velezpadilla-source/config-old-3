#!/usr/bin/env bash
set -euo pipefail

APK="${1:?usage: smoke_xziel_nacht_hybrid_android.sh <apk> <out-dir>}"
OUT="${2:-dist/android-hybrid-smoke}"
PKG="com.xziel.hybrid"
ACTIVITY="com.winlator.XzielBootActivity"

mkdir -p "$OUT"

adb wait-for-device
adb shell getprop ro.product.cpu.abi | tr -d '\r' | tee "$OUT/device-abi.txt"
grep -q '^arm64-v8a$' "$OUT/device-abi.txt"

adb shell df -h /data | tee "$OUT/data-before.txt"
adb install -r -g "$APK" | tee "$OUT/adb-install.txt"
adb shell pm path "$PKG" | tee "$OUT/pm-path.txt"
grep -q '^package:' "$OUT/pm-path.txt"

adb shell am force-stop "$PKG" || true
adb logcat -c
adb shell am start -W -n "$PKG/$ACTIVITY" | tee "$OUT/am-start.txt"

ready=0
failed=0
for _ in $(seq 1 300); do
  adb logcat -d -v threadtime > "$OUT/logcat.txt" || true

  if grep -Eq     'FATAL EXCEPTION|Fatal signal|SIGSEGV|SIGABRT|No space left on device|embedded EXE (byte count|SHA-256) mismatch|XZIEL startup failed|XZIEL game setup failed|Unable to start activity'     "$OUT/logcat.txt"; then
    failed=1
    break
  fi

  if grep -q 'XZIEL-HYBRID.*FIRST_RENDERABLE_WINDOW' "$OUT/logcat.txt"; then
    ready=1
    break
  fi

  sleep 5
done

adb shell df -h /data | tee "$OUT/data-after.txt" || true
adb shell ps -A | grep -E 'xziel|winlator|box64|wine' | tee "$OUT/processes.txt" || true

grep -E   'XZIEL-HYBRID|box64|wine|vortek|gladio|FATAL EXCEPTION|Fatal signal|SIGSEGV|SIGABRT|No space left'   "$OUT/logcat.txt" | tail -n 2500 > "$OUT/boot-markers.txt" || true

if [[ "$failed" == "1" || "$ready" != "1" ]]; then
  echo "XZIEL_ANDROID_HYBRID_GATE failed=$failed ready=$ready"
  cat "$OUT/boot-markers.txt" || true
  exit 93
fi

for marker in   BOOT_ACTIVITY_START   ROOTFS_READY   CONTAINER_READY   LAUNCH_XSERVER   XSERVER_ACTIVITY_START   XSERVER_ENV_SETUP_BEGIN   XSERVER_ENVIRONMENT_STARTED   FIRST_RENDERABLE_WINDOW; do
  grep -q "XZIEL-HYBRID.*$marker" "$OUT/logcat.txt"
done

adb exec-out screencap -p > "$OUT/first-renderable-window.png"
test -s "$OUT/first-renderable-window.png"

echo "XZIEL_ANDROID_HYBRID_FIRST_RENDERABLE_WINDOW_GREEN"
