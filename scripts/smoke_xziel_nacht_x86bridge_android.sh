#!/usr/bin/env bash
set -euo pipefail

APK="${1:?APK path required}"
OUT="dist/android-x86bridge-smoke"
XZIEL_PACKAGE="com.xzielapp"
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
adb shell pm path ${XZIEL_PACKAGE} | tee "$OUT/pm-path.txt"
grep -q '^package:' "$OUT/pm-path.txt"
echo "XZIEL_X86BRIDGE_APK_INSTALL_GREEN"

adb shell am force-stop ${XZIEL_PACKAGE} || true
adb logcat -c
adb shell am start -W   -n ${XZIEL_PACKAGE}/com.winlator.XzielBootActivity   | tee "$OUT/am-start.txt"

sleep 3
adb logcat -d -v threadtime > "$OUT/logcat-launch.txt" || true
grep -E 'XZIEL-HYBRID|AndroidRuntime|FATAL EXCEPTION|Fatal signal|SIGSEGV|SIGABRT'   "$OUT/logcat-launch.txt" | tail -n 1000 > "$OUT/boot-markers-launch.txt" || true

grep -q 'XZIEL-HYBRID.*BOOT_ACTIVITY_START' "$OUT/logcat-launch.txt"
echo "XZIEL_X86BRIDGE_ACTIVITY_LAUNCH_GREEN"

ready=0
failed=0
last_marker="BOOT_ACTIVITY_START"
pie_retry=0

for i in $(seq 1 36); do
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

  if grep -q 'XZIEL-HYBRID.*GUEST_EXIT' "$OUT/logcat.txt"; then
    if [[ "$pie_retry" == "0" ]] && grep -q 'position-independent executables' "$OUT/logcat.txt" && [[ -n "${XZIEL_BOX64_PIE:-}" ]] && [[ -s "$XZIEL_BOX64_PIE" ]]; then
      pie_retry=1
      echo "XZIEL_X86BRIDGE_NONPIE_BOX64_DETECTED"
      sha256sum "$XZIEL_BOX64_PIE" | tee "$OUT/box64-pie-injected.sha256"

      adb shell am force-stop ${XZIEL_PACKAGE} || true

      # Execute PIE according to its actual ELF runtime contract.
      # Bionic PIE has /system/bin/linker64 and is launched directly.
      # glibc static-PIE has no INTERP at all and must also be launched directly.
      # Only dynamically linked glibc PIE needs the explicit rootfs loader.
      if readelf -l "$XZIEL_BOX64_PIE" 2>/dev/null | grep -q '/system/bin/linker64'; then
        adb shell "run-as ${XZIEL_PACKAGE} sh -c 'cat > files/rootfs/usr/local/bin/box64'" < "$XZIEL_BOX64_PIE"
        adb shell run-as ${XZIEL_PACKAGE} chmod 700 files/rootfs/usr/local/bin/box64
        adb shell run-as ${XZIEL_PACKAGE} ls -l files/rootfs/usr/local/bin/box64 | tee "$OUT/box64-pie-installed.txt"
        echo "XZIEL_X86BRIDGE_BIONIC_PIE_BOX64_INJECTED"
      elif ! readelf -l "$XZIEL_BOX64_PIE" 2>/dev/null | grep -q 'INTERP'; then
        adb shell "run-as ${XZIEL_PACKAGE} sh -c 'cat > files/rootfs/usr/local/bin/box64'" < "$XZIEL_BOX64_PIE"
        adb shell run-as ${XZIEL_PACKAGE} chmod 700 files/rootfs/usr/local/bin/box64
        adb shell run-as ${XZIEL_PACKAGE} ls -l files/rootfs/usr/local/bin/box64 | tee "$OUT/box64-pie-installed.txt"
        echo "XZIEL_X86BRIDGE_GLIBC_STATIC_PIE_BOX64_INJECTED"
      else
        adb shell "run-as ${XZIEL_PACKAGE} sh -c 'cat > files/rootfs/usr/local/bin/box64.real'" < "$XZIEL_BOX64_PIE"
        adb shell run-as ${XZIEL_PACKAGE} chmod 700 files/rootfs/usr/local/bin/box64.real

        cat > "$OUT/box64-glibc-wrapper.sh" <<'EOF'
#!/system/bin/sh
ROOT=/data/data/com.xzielapp/files/rootfs
exec "$ROOT/lib/ld-linux-aarch64.so.1" \
  --library-path "$ROOT/lib:$ROOT/usr/lib" \
  "$ROOT/usr/local/bin/box64.real" "$@"
EOF
        adb shell "run-as ${XZIEL_PACKAGE} sh -c 'cat > files/rootfs/usr/local/bin/box64'" < "$OUT/box64-glibc-wrapper.sh"
        adb shell run-as ${XZIEL_PACKAGE} chmod 700 files/rootfs/usr/local/bin/box64
        adb shell run-as ${XZIEL_PACKAGE} ls -l files/rootfs/usr/local/bin/box64 files/rootfs/usr/local/bin/box64.real | tee "$OUT/box64-pie-installed.txt"
        echo "XZIEL_X86BRIDGE_GLIBC_LOADER_WRAPPER_INJECTED"
      fi

      adb logcat -c
      adb shell am start -W -n ${XZIEL_PACKAGE}/com.winlator.XzielBootActivity | tee "$OUT/am-restart-pie.txt"
      sleep 3
      last_marker="PIE_BOX64_RELAUNCH"
      continue
    fi

    last_marker="GUEST_EXIT"
    failed=1
    echo "XZIEL_X86BRIDGE_GUEST_EXIT_DETECTED"
    break
  fi

  if grep -q 'XZIEL-PROCESS.*exec failed' "$OUT/logcat.txt"; then
    last_marker="PROCESS_EXEC_FAILED"
    failed=1
    echo "XZIEL_X86BRIDGE_PROCESS_EXEC_FAILED"
    break
  fi

  printf 'probe=%s last_marker=%s\n' "$i" "$last_marker"

  if (( i % 6 == 0 )); then
    adb shell ps -A | grep -E 'xziel|winlator|box64|wine' | tee "$OUT/processes-probe-$i.txt" || true
  fi

  if [[ "$last_marker" == "FIRST_RENDERABLE_WINDOW" ]]; then
    ready=1
    break
  fi
  sleep 5
done

adb shell df -h /data | tee "$OUT/data-after-boot.txt" || true

# Preserve the guest's redirected stdout/stderr before any cleanup. The XZIEL
# launcher writes this file specifically for x86-bridge diagnosis.
adb shell run-as ${XZIEL_PACKAGE} sh -c 'if [ -f files/rootfs/tmp/xziel-guest-output.log ]; then cat files/rootfs/tmp/xziel-guest-output.log; fi' \
  > "$OUT/xziel-guest-output.log" 2>&1 || true
echo "XZIEL_X86BRIDGE_GUEST_FILE_CAPTURE_BEGIN"
tail -n 1200 "$OUT/xziel-guest-output.log" || true
echo "XZIEL_X86BRIDGE_GUEST_FILE_CAPTURE_END"

adb shell run-as ${XZIEL_PACKAGE} sh -c 'ls -la files/rootfs/tmp files/rootfs/tmp/shm 2>&1; find files/rootfs/tmp/shm -maxdepth 1 -type f -ls 2>/dev/null | head -n 200' \
  > "$OUT/shm-state.txt" 2>&1 || true
echo "XZIEL_X86BRIDGE_SHM_STATE"
cat "$OUT/shm-state.txt" || true

adb shell ps -A | grep -E 'xziel|winlator|box64|wine' | tee "$OUT/processes.txt" || true
adb shell dumpsys activity activities   | grep -E "mResumedActivity|topResumedActivity|${XZIEL_PACKAGE}"   | tee "$OUT/activity-final.txt" || true

adb shell run-as ${XZIEL_PACKAGE} sh -c 'cat files/rootfs/tmp/xziel-guest-output.log 2>/dev/null' \
  > "$OUT/guest-output.txt" || true
if [[ -s "$OUT/guest-output.txt" ]]; then
  echo "XZIEL_X86BRIDGE_GUEST_OUTPUT_CAPTURED bytes=$(wc -c < "$OUT/guest-output.txt")"
  tail -n 500 "$OUT/guest-output.txt" || true
else
  echo "XZIEL_X86BRIDGE_GUEST_OUTPUT_EMPTY"
fi

# Preserve the guest stdout/stderr file written by the APK's ProcessHelper.
# This is the authoritative Wine/Box64 error stream for x86-bridge runs.
adb shell run-as ${XZIEL_PACKAGE} sh -c 'test -f files/rootfs/tmp/xziel-guest-output.log && cat files/rootfs/tmp/xziel-guest-output.log' \
  > "$OUT/xziel-guest-output.log" 2>/dev/null || true
if [[ -s "$OUT/xziel-guest-output.log" ]]; then
  echo "XZIEL_X86BRIDGE_GUEST_OUTPUT_CAPTURED bytes=$(wc -c < "$OUT/xziel-guest-output.log")"
  tail -n 300 "$OUT/xziel-guest-output.log" || true
else
  echo "XZIEL_X86BRIDGE_GUEST_OUTPUT_EMPTY"
fi

adb shell run-as ${XZIEL_PACKAGE} sh -c 'find files/rootfs -type f \( -name "ld-linux-x86-64.so.2" -o -name "ld-linux*.so*" -o -path "*/bin/wine" -o -path "*/bin/wine64" \) -print 2>/dev/null | sort' \
  | tee "$OUT/rootfs-runtime-paths.txt" || true
echo "XZIEL_X86BRIDGE_ROOTFS_RUNTIME_PATHS"
cat "$OUT/rootfs-runtime-paths.txt" || true

# Preserve the guest stdout/stderr file created by ProcessHelper. This is the
# authoritative diagnostic for silent Box64/Wine child exits.
adb shell run-as ${XZIEL_PACKAGE} sh -c 'if [ -f files/rootfs/tmp/xziel-guest-output.log ]; then cat files/rootfs/tmp/xziel-guest-output.log; fi' \
  > "$OUT/xziel-guest-output.log" 2>/dev/null || true
echo "XZIEL_X86BRIDGE_GUEST_OUTPUT_BEGIN"
tail -n 1200 "$OUT/xziel-guest-output.log" || true
echo "XZIEL_X86BRIDGE_GUEST_OUTPUT_END"

adb shell run-as ${XZIEL_PACKAGE} sh -c 'if [ -d files/rootfs/tmp/shm ]; then ls -la files/rootfs/tmp/shm; fi' \
  > "$OUT/xziel-shm-state.txt" 2>/dev/null || true
echo "XZIEL_X86BRIDGE_SHM_STATE"
cat "$OUT/xziel-shm-state.txt" || true

grep -E   'XZIEL-HYBRID|XZIEL-GUEST|XZIEL-PROCESS|box64|wine|vortek|gladio|AndroidRuntime|FATAL EXCEPTION|Fatal signal|SIGSEGV|SIGABRT|No space left'   "$OUT/logcat.txt" | tail -n 4000 > "$OUT/boot-markers.txt" || true

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
