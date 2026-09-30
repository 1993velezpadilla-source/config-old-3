#!/usr/bin/env bash
set +e

OUT=/tmp/xchurch-api35
mkdir -p "$OUT/screens"

{
  echo "DEVICE_ABI=$(adb shell getprop ro.product.cpu.abi | tr -d '\r')"
  echo "DEVICE_ABILIST=$(adb shell getprop ro.product.cpu.abilist | tr -d '\r')"
  echo "NATIVE_BRIDGE=$(adb shell getprop ro.dalvik.vm.native.bridge | tr -d '\r')"
  echo "SDK=$(adb shell getprop ro.build.version.sdk | tr -d '\r')"
} | tee "$OUT/device.txt"

adb install -r -d "$OUT/xchurch.apk" > "$OUT/install.log" 2>&1
INSTALL_RC=$?
echo "INSTALL_RC=$INSTALL_RC" | tee "$OUT/status.txt"
cat "$OUT/install.log" | tee -a "$OUT/status.txt"

if [ "$INSTALL_RC" -eq 0 ]; then
  adb shell settings put system accelerometer_rotation 0 || true
  adb shell settings put system user_rotation 1 || true
  adb shell settings put secure immersive_mode_confirmations confirmed || true
  adb shell pm grant com.activision.boz android.permission.WRITE_EXTERNAL_STORAGE 2>/dev/null || true
  adb shell pm grant com.activision.boz android.permission.READ_EXTERNAL_STORAGE 2>/dev/null || true
  adb shell appops set com.activision.boz MANAGE_EXTERNAL_STORAGE allow 2>/dev/null || true

  adb logcat -c
  adb shell am force-stop com.activision.boz
  adb shell am start -W -n com.activision.boz/.Main > "$OUT/launch.txt" 2>&1
  START_RC=$?
  echo "START_RC=$START_RC" | tee -a "$OUT/status.txt"
  cat "$OUT/launch.txt" | tee -a "$OUT/status.txt"

  # Android's first immersive-mode education overlay can hide the game.
  # Dismiss it explicitly if it appears; harmless if it does not.
  sleep 2
  adb shell input tap 1700 520 >/dev/null 2>&1 || true

  sleep 3
  adb exec-out screencap -p > "$OUT/screens/boot_05s.png"
  sleep 10
  adb exec-out screencap -p > "$OUT/screens/boot_15s.png"
  sleep 15
  adb exec-out screencap -p > "$OUT/screens/boot_30s.png"
  sleep 30
  adb exec-out screencap -p > "$OUT/screens/boot_60s.png"
else
  adb exec-out screencap -p > "$OUT/screens/install_failure.png"
fi

adb logcat -d -v threadtime > "$OUT/logcat.txt" 2>&1
adb shell dumpsys activity activities > "$OUT/activities.txt" 2>&1
adb shell dumpsys window windows > "$OUT/window.txt" 2>&1
PID="$(adb shell pidof com.activision.boz 2>/dev/null | tr -d '\r' || true)"
echo "PID=$PID" | tee -a "$OUT/status.txt"

grep -Eai   'FATAL EXCEPTION|Fatal signal|SIGSEGV|SIGABRT|UnsatisfiedLinkError|dlopen failed|native bridge|houdini|ndk_translation|xchurch|kino|Marmalade|s3e|activision|boz'   "$OUT/logcat.txt" | tail -400 > "$OUT/logcat-highlights.txt" || true

echo "XZIEL_API35_CAPTURE_SCRIPT_DONE"
exit 0
