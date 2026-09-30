#!/usr/bin/env bash
set -euo pipefail

APK="${1:?APK path required}"
OUT="dist/android-x86bridge-smoke"
mkdir -p "$OUT"

adb wait-for-device
primary="$(adb shell getprop ro.product.cpu.abi | tr -d '\r')"
abilist="$(adb shell getprop ro.product.cpu.abilist | tr -d '\r')"
bridge="$(adb shell getprop ro.dalvik.vm.native.bridge | tr -d '\r')"
bridge_exec="$(adb shell getprop ro.enable.native.bridge.exec | tr -d '\r')"

printf '%s\n' "$primary" | tee "$OUT/primary-abi.txt"
printf '%s\n' "$abilist" | tee "$OUT/abi-list.txt"
printf '%s\n' "$bridge" | tee "$OUT/native-bridge.txt"
printf '%s\n' "$bridge_exec" | tee "$OUT/native-bridge-exec.txt"

echo "XZIEL_X86BRIDGE primary=$primary abilist=$abilist bridge=$bridge bridge_exec=$bridge_exec"

grep -q 'x86_64' "$OUT/abi-list.txt"
if ! grep -q 'arm64-v8a' "$OUT/abi-list.txt"; then
  echo "XZIEL_X86BRIDGE_NO_ARM64_SUPPORT"
  exit 71
fi
echo "XZIEL_X86BRIDGE_ARM64_TRANSLATION_AVAILABLE"

adb shell df -h /data | tee "$OUT/data-before-install.txt"
adb install -r -g --abi arm64-v8a "$APK" | tee "$OUT/adb-install.txt"
grep -q 'Success' "$OUT/adb-install.txt"
adb shell pm path com.xziel.hybrid | tee "$OUT/pm-path.txt"
grep -q '^package:' "$OUT/pm-path.txt"
echo "XZIEL_X86BRIDGE_APK_INSTALL_GREEN"

adb shell am force-stop com.xziel.hybrid || true
adb logcat -c
adb shell am start -W   -n com.xziel.hybrid/com.winlator.XzielBootActivity   | tee "$OUT/am-start.txt"

sleep 3
adb logcat -d -v threadtime > "$OUT/logcat-launch.txt" || true
grep -E 'XZIEL-HYBRID|AndroidRuntime|FATAL EXCEPTION|Fatal signal|SIGSEGV|SIGABRT'   "$OUT/logcat-launch.txt" | tail -n 1000 > "$OUT/boot-markers-launch.txt" || true

grep -q 'XZIEL-HYBRID.*BOOT_ACTIVITY_START' "$OUT/logcat-launch.txt"
echo "XZIEL_X86BRIDGE_ACTIVITY_LAUNCH_GREEN"

ready=0
failed=0
last_marker="BOOT_ACTIVITY_START"

for i in $(seq 1 180); do
  adb logcat -d -v threadtime > "$OUT/logcat.txt" || true

  if grep -Eq     'FATAL EXCEPTION|Fatal signal|SIGSEGV|SIGABRT|No space left on device|embedded EXE (byte count|SHA-256) mismatch|XZIEL startup failed|XZIEL game setup failed|Unable to start activity'     "$OUT/logcat.txt"; then
    failed=1
    break
  fi

  for marker in     ROOTFS_READY     CONTAINER_READY     LAUNCH_XSERVER     XSERVER_ACTIVITY_START     XSERVER_ENV_SETUP_BEGIN     XSERVER_ENVIRONMENT_STARTED     FIRST_RENDERABLE_WINDOW; do
    if grep -q "XZIEL-HYBRID.*$marker" "$OUT/logcat.txt"; then
      last_marker="$marker"
    fi
  done

  printf 'probe=%s last_marker=%s\n' "$i" "$last_marker"

  if [[ "$last_marker" == "FIRST_RENDERABLE_WINDOW" ]]; then
    ready=1
    break
  fi
  sleep 5
done

adb shell df -h /data | tee "$OUT/data-after-boot.txt" || true
adb shell ps -A | grep -E 'xziel|winlator|box64|wine' | tee "$OUT/processes.txt" || true
adb shell dumpsys activity activities   | grep -E 'mResumedActivity|topResumedActivity|com.xziel.hybrid'   | tee "$OUT/activity-final.txt" || true

grep -E   'XZIEL-HYBRID|box64|wine|vortek|gladio|AndroidRuntime|FATAL EXCEPTION|Fatal signal|SIGSEGV|SIGABRT|No space left'   "$OUT/logcat.txt" | tail -n 4000 > "$OUT/boot-markers.txt" || true

adb exec-out screencap -p > "$OUT/final-screen.png" || true

echo "last_marker=$last_marker" | tee "$OUT/result.txt"
echo "ready=$ready" | tee -a "$OUT/result.txt"
echo "failed=$failed" | tee -a "$OUT/result.txt"

if [[ "$failed" == "1" || "$ready" != "1" ]]; then
  echo "XZIEL_X86BRIDGE_RUNTIME_NOT_GREEN last_marker=$last_marker failed=$failed"
  tail -n 700 "$OUT/boot-markers.txt" || true
  exit 93
fi

echo "XZIEL_X86BRIDGE_FIRST_RENDERABLE_WINDOW_GREEN"
