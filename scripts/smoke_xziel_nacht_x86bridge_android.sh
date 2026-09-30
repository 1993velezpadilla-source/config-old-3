# XZIEL_GATE_RUNTIME_WINESERVER_APK27_20260930
# XZIEL_GATE_DIRECT_NACHT_APK26_20260930
# XZIEL_GATE_FRESH_DIRECT_NACHT_APK_26_20260930
# XZIEL_GATE_BIONIC_PIE_X86_64_FREETYPE_20260930
#!/usr/bin/env bash
set -euo pipefail

APK="${1:?APK path required}"
OUT="dist/android-x86bridge-smoke"
XZIEL_PACKAGE="com.xzielapp"
mkdir -p "$OUT"

# APK27+ owns wineserver lifecycle itself. Keep the smoke from injecting a
# second foreground server so this run proves the standalone APK path.
XZIEL_PRELAUNCH_DEEP_DIAG="${XZIEL_PRELAUNCH_DEEP_DIAG:-0}"
export XZIEL_PRELAUNCH_DEEP_DIAG
echo "XZIEL_PURE_APK_RUNTIME_MODE deep_diag=$XZIEL_PRELAUNCH_DEEP_DIAG"

# FreeType gate: use the patched Bionic Box64 native wrapper. The custom
# FT_Get_WinFNT_Header GOM shim is provided by the injected Box64 binary.
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
    # New diagnostic APK persists guest stdout/stderr instead of mirroring it
    # to logcat. Pull it immediately so the original non-PIE bootstrap failure
    # still triggers the Bionic PIE replacement path.
    adb exec-out run-as ${XZIEL_PACKAGE} cat files/rootfs/tmp/xziel-guest-output.log \
      > "$OUT/guest-live.txt" 2>/dev/null || true
    nonpie_detected=0
    if grep -q 'position-independent executables' "$OUT/logcat.txt" || \
       grep -q 'position-independent executables' "$OUT/guest-live.txt"; then
      nonpie_detected=1
    fi

    if [[ "$pie_retry" == "0" && "$nonpie_detected" == "1" ]] && [[ -n "${XZIEL_BOX64_PIE:-}" ]] && [[ -s "$XZIEL_BOX64_PIE" ]]; then
      pie_retry=1
      echo "XZIEL_X86BRIDGE_NONPIE_BOX64_DETECTED"
      sha256sum "$XZIEL_BOX64_PIE" | tee "$OUT/box64-pie-injected.sha256"

      adb shell am force-stop ${XZIEL_PACKAGE} || true

      # Execute PIE according to its actual ELF runtime contract.
      # Bionic PIE has /system/bin/linker64 and is launched directly.
      # glibc static-PIE has no INTERP at all and must also be launched directly.
      # Only dynamically linked glibc PIE needs the explicit rootfs loader.
      if readelf -l "$XZIEL_BOX64_PIE" 2>/dev/null | grep -q '/system/bin/linker64'; then
        # Bionic PIE is the Android-executable Box64 path. Keep the binary as
        # box64.real and wrap it so both the activity relaunch and CI probes
        # always see the isolated x86_64 guest FreeType bundle.
        adb shell "run-as ${XZIEL_PACKAGE} sh -c 'cat > files/rootfs/usr/local/bin/box64.real'" < "$XZIEL_BOX64_PIE"
        adb shell run-as ${XZIEL_PACKAGE} chmod 700 files/rootfs/usr/local/bin/box64.real
        cat > "$OUT/box64-bionic-wrapper.sh" <<'EOF'
#!/system/bin/sh
ROOT=/data/user/0/com.xzielapp/files/rootfs
export BOX64_LD_LIBRARY_PATH="$ROOT/lib/x86_64-linux-gnu"
exec "$ROOT/usr/local/bin/box64.real" "$@"
EOF
        adb shell "run-as ${XZIEL_PACKAGE} sh -c 'cat > files/rootfs/usr/local/bin/box64'" < "$OUT/box64-bionic-wrapper.sh"
        adb shell run-as ${XZIEL_PACKAGE} chmod 700 files/rootfs/usr/local/bin/box64
        adb shell run-as ${XZIEL_PACKAGE} ls -l files/rootfs/usr/local/bin/box64 files/rootfs/usr/local/bin/box64.real | tee "$OUT/box64-pie-installed.txt"
        echo "XZIEL_X86BRIDGE_BIONIC_PIE_BOX64_INJECTED"
      elif ! readelf -l "$XZIEL_BOX64_PIE" 2>/dev/null | grep -q 'INTERP'; then
        # glibc static-PIE Box64 can safely start under ndk_translation without
        # an ELF interpreter. Keep it as .real and launch it through Android sh
        # so native ARM64 glibc libraries from the Winlator rootfs are visible
        # to Box64 wrappers, while x86_64 guest search stays isolated.
        adb shell "run-as ${XZIEL_PACKAGE} sh -c 'cat > files/rootfs/usr/local/bin/box64.real'" < "$XZIEL_BOX64_PIE"
        adb shell run-as ${XZIEL_PACKAGE} chmod 700 files/rootfs/usr/local/bin/box64.real
        cat > "$OUT/box64-glibc-static-wrapper.sh" <<'EOF'
#!/system/bin/sh
ROOT=/data/user/0/com.xzielapp/files/rootfs
export LD_LIBRARY_PATH="$ROOT/usr/lib:$ROOT/lib"
export BOX64_LD_LIBRARY_PATH="$ROOT/lib/x86_64-linux-gnu"
exec "$ROOT/usr/local/bin/box64.real" "$@"
EOF
        adb shell "run-as ${XZIEL_PACKAGE} sh -c 'cat > files/rootfs/usr/local/bin/box64'" < "$OUT/box64-glibc-static-wrapper.sh"
        adb shell run-as ${XZIEL_PACKAGE} chmod 700 files/rootfs/usr/local/bin/box64
        adb shell run-as ${XZIEL_PACKAGE} ls -l files/rootfs/usr/local/bin/box64 files/rootfs/usr/local/bin/box64.real | tee "$OUT/box64-pie-installed.txt"
        echo "XZIEL_X86BRIDGE_GLIBC_STATIC_PIE_BOX64_WRAPPER_INJECTED"
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

      echo "XZIEL_X86BRIDGE_FREETYPE_MODE native-bionic-plus-winfnt-shim"

      # Deep compatibility probes are useful after a failure, but running them
      # before every relaunch can delay or retain Wine children. Fast launch is
      # the default now: get Nacht to the real XServer first.
      if [[ "${XZIEL_PRELAUNCH_DEEP_DIAG:-1}" == "1" ]]; then
      # Direct runtime probe: distinguish Box64/native-bridge failure from
      # Wine/winhandler/game startup failure before relaunching the Android UI.
      adb shell "run-as ${XZIEL_PACKAGE} sh -c 'ROOT=files/rootfs; TMPDIR=\$ROOT/tmp BOX64_LOG=2 BOX64_LD_LIBRARY_PATH=\$ROOT/lib/x86_64-linux-gnu \$ROOT/usr/local/bin/box64 --version'" \
        > "$OUT/box64-direct-probe.txt" 2>&1 || true
      adb shell "run-as ${XZIEL_PACKAGE} sh -c 'ROOT=files/rootfs; TMPDIR=\$ROOT/tmp BOX64_LOG=2 BOX64_LD_LIBRARY_PATH=\$ROOT/lib/x86_64-linux-gnu PATH=\$ROOT/opt/wine/bin:/system/bin \$ROOT/usr/local/bin/box64 \$ROOT/opt/wine/bin/wine --version'" \
        > "$OUT/wine-direct-probe.txt" 2>&1 || true
      adb shell "run-as ${XZIEL_PACKAGE} sh -c 'ROOT=files/rootfs; TMPDIR=\$ROOT/tmp BOX64_LOG=2 BOX64_LD_LIBRARY_PATH=\$ROOT/lib/x86_64-linux-gnu PATH=\$ROOT/opt/wine/bin:/system/bin \$ROOT/usr/local/bin/box64 \$ROOT/opt/wine/bin/wineserver --version'" \
        > "$OUT/wineserver-direct-probe.txt" 2>&1 || true
      echo "XZIEL_X86BRIDGE_DIRECT_PROBE_BOX64"
      tail -n 200 "$OUT/box64-direct-probe.txt" || true
      echo "XZIEL_X86BRIDGE_DIRECT_PROBE_WINE"
      tail -n 300 "$OUT/wine-direct-probe.txt" || true
      echo "XZIEL_X86BRIDGE_DIRECT_PROBE_WINESERVER"
      tail -n 300 "$OUT/wineserver-direct-probe.txt" || true
      echo "XZIEL_X86BRIDGE_WINFNT_SHIM_EXPECTED"
      echo "XZIEL_X86BRIDGE_FREETYPE_ROOTFS_CENSUS"
      echo "XZIEL_X86BRIDGE_FREETYPE_MODE native-bionic-plus-winfnt-shim"
      adb shell "run-as ${XZIEL_PACKAGE} sh -c 'ROOT=/data/user/0/com.xzielapp/files/rootfs; find \$ROOT/lib \$ROOT/usr/lib -type f -o -type l 2>/dev/null | grep -E \"/libfreetype\\.so|/libfontconfig\\.so\" | sort | head -n 80'" \
        > "$OUT/freetype-rootfs-census.txt" 2>&1 || true
      cat "$OUT/freetype-rootfs-census.txt" || true
      echo "XZIEL_X86BRIDGE_FREETYPE_SYMBOL_PROBE"
      adb shell "run-as ${XZIEL_PACKAGE} sh -c 'ls -l files/rootfs/usr/lib/libfreetype.so* files/rootfs/usr/lib/libfontconfig.so* 2>/dev/null'" \
        > "$OUT/freetype-rootfs-links.txt" 2>&1 || true
      cat "$OUT/freetype-rootfs-links.txt" || true
      adb exec-out run-as ${XZIEL_PACKAGE} cat files/rootfs/usr/lib/libfreetype.so.6.20.2 \
        > "$OUT/rootfs-libfreetype.so.6.20.2" 2>/dev/null || true
      if [[ -s "$OUT/rootfs-libfreetype.so.6.20.2" ]]; then
        file "$OUT/rootfs-libfreetype.so.6.20.2" | tee "$OUT/rootfs-libfreetype.file.txt" || true
        readelf -h "$OUT/rootfs-libfreetype.so.6.20.2" | tee "$OUT/rootfs-libfreetype.elf-header.txt" || true
        readelf -d "$OUT/rootfs-libfreetype.so.6.20.2" | tee "$OUT/rootfs-libfreetype.dynamic.txt" || true
        readelf -Ws "$OUT/rootfs-libfreetype.so.6.20.2" \
          | grep -E 'FT_Get_WinFNT_Header|FT_Init_FreeType' \
          | tee "$OUT/rootfs-libfreetype.symbols.txt" || true
        sha256sum "$OUT/rootfs-libfreetype.so.6.20.2" | tee "$OUT/rootfs-libfreetype.sha256"
        if grep -q 'FT_Get_WinFNT_Header' "$OUT/rootfs-libfreetype.symbols.txt"; then
          echo "XZIEL_X86BRIDGE_FREETYPE_SYMBOL_PRESENT"
        else
          echo "XZIEL_X86BRIDGE_FREETYPE_SYMBOL_MISSING"
        fi
      else
        echo "XZIEL_X86BRIDGE_FREETYPE_BINARY_PULL_FAILED"
      fi
      echo "XZIEL_X86BRIDGE_ANDROID_FREETYPE_CENSUS"
      adb shell "sh -c 'find /system/lib64 /apex -type f -o -type l 2>/dev/null | grep -E \"/(libft2|libfreetype)\\.so\" | sort | head -n 80'" \
        > "$OUT/android-freetype-census.txt" 2>&1 || true
      cat "$OUT/android-freetype-census.txt" || true

      # Persistent foreground wineserver path. The Android/native-translation
      # bridge cannot safely resume wineserver after its internal fork(), but
      # wineserver -f is healthy and creates the real prefix socket. Pair it with
      # -p so it survives the warmup client and remains available to the launcher. Keep one
      # foreground server alive across the first (slow) Wine prefix warmup and
      # the Android relaunch instead of killing it after a short diagnostic.
      timeout 10s adb shell "run-as ${XZIEL_PACKAGE} sh -c 'ROOT=/data/user/0/com.xzielapp/files/rootfs; rm -f \$ROOT/tmp/xziel-wineserver-fg.log \$ROOT/tmp/xziel-wineserver-fg.pid; HOME=\$ROOT/home/xuser USER=xuser TMPDIR=\$ROOT/tmp PATH=\$ROOT/opt/wine/bin:\$ROOT/usr/local/bin:\$ROOT/usr/bin:/system/bin BOX64_DYNAREC=0 BOX64_NOBANNER=1 BOX64_LOG=0 BOX64_LD_LIBRARY_PATH=\$ROOT/lib/x86_64-linux-gnu ANDROID_SYSVSHM_SERVER=\$ROOT/tmp/.sysvshm/SM0 WINEPREFIX=\$ROOT/home/xuser/.wine WINEESYNC=0 WINEFSYNC=0 \$ROOT/usr/local/bin/box64 \$ROOT/opt/wine/bin/wineserver -f -p > \$ROOT/tmp/xziel-wineserver-fg.log 2>&1 & echo \$! > \$ROOT/tmp/xziel-wineserver-fg.pid'" \
        > "$OUT/wineserver-fg-start.txt" 2>&1 || true
      sleep 2
      adb exec-out run-as ${XZIEL_PACKAGE} cat files/rootfs/tmp/xziel-wineserver-fg.pid > "$OUT/wineserver-fg.pid" 2>/dev/null || true
      adb shell "run-as ${XZIEL_PACKAGE} sh -c 'ROOT=/data/user/0/com.xzielapp/files/rootfs; echo PID=\$(cat \$ROOT/tmp/xziel-wineserver-fg.pid 2>/dev/null); ps -A | grep -E \"box64|wineserver\" || true; find \$ROOT/tmp -maxdepth 3 -type s -print 2>/dev/null | sort'" \
        > "$OUT/wineserver-fg-state.txt" 2>&1 || true

      # First Wine use can spend a long time importing/normalizing the prefix
      # registry under interpreter-only Box64. Previous 20s probes killed the
      # healthy server while the client was blocked waiting for that
      # initialization. Keep Box64 tracing off here: per-call tracing inflated
      # the server log to tens of MB and made registry import artificially slow.
      # Give the same quiet server a bounded first-prefix warmup.
      echo "XZIEL_X86BRIDGE_DIRECT_CMD_EXE_PROBE"
      adb shell "run-as ${XZIEL_PACKAGE} sh -c '
        ROOT=/data/user/0/com.xzielapp/files/rootfs
        echo XZIEL_PREFIX_LINK
        ls -ld \$ROOT/home/xuser \$ROOT/home/xuser-1 2>/dev/null || true
        echo XZIEL_WINDOWS_EXECUTABLE_CENSUS
        ls -l \
          \$ROOT/home/xuser/.wine/drive_c/windows/system32/cmd.exe \
          \$ROOT/home/xuser/.wine/drive_c/windows/winhandler.exe \
          \$ROOT/home/xuser/.wine/drive_c/XZIEL/Nacht-Chronicles-XZIEL.exe \
          2>/dev/null || true
        wc -c \
          \$ROOT/home/xuser/.wine/drive_c/windows/system32/cmd.exe \
          \$ROOT/home/xuser/.wine/drive_c/windows/winhandler.exe \
          \$ROOT/home/xuser/.wine/drive_c/XZIEL/Nacht-Chronicles-XZIEL.exe \
          2>/dev/null || true
        test -s \$ROOT/home/xuser/.wine/drive_c/windows/system32/cmd.exe
        test -s \$ROOT/home/xuser/.wine/drive_c/windows/winhandler.exe
        test -s \$ROOT/home/xuser/.wine/drive_c/XZIEL/Nacht-Chronicles-XZIEL.exe
      '" > "$OUT/windows-executable-census.txt" 2>&1 || true
      cat "$OUT/windows-executable-census.txt" || true

      # Use a DOS path here, not the Unix backing file. Passing the Unix path to
      # Wine can route through start/ShellExecute and hide whether cmd.exe itself
      # is healthy.
      timeout 240s adb shell "run-as ${XZIEL_PACKAGE} sh -c 'ROOT=/data/user/0/com.xzielapp/files/rootfs; HOME=\$ROOT/home/xuser USER=xuser TMPDIR=\$ROOT/tmp PATH=\$ROOT/opt/wine/bin:\$ROOT/usr/local/bin:\$ROOT/usr/bin:/system/bin BOX64_DYNAREC=0 BOX64_NOBANNER=1 BOX64_LOG=1 BOX64_DLSYM_ERROR=1 BOX64_LD_LIBRARY_PATH=\$ROOT/lib/x86_64-linux-gnu ANDROID_SYSVSHM_SERVER=\$ROOT/tmp/.sysvshm/SM0 WINEPREFIX=\$ROOT/home/xuser/.wine WINEDEBUG=+process,+server,+module,+seh WINEESYNC=0 WINEFSYNC=0 \$ROOT/usr/local/bin/box64 \$ROOT/opt/wine/bin/wine C:\\\\windows\\\\system32\\\\cmd.exe /c ver; rc=\$?; echo XZIEL_PRESTARTED_CMD_STATUS=\$rc; exit \$rc'" \
        > "$OUT/wine-with-prestarted-server.txt" 2>&1 || true

      adb exec-out run-as ${XZIEL_PACKAGE} cat files/rootfs/tmp/xziel-wineserver-fg.log > "$OUT/wineserver-fg.log" 2>/dev/null || true
      adb shell "run-as ${XZIEL_PACKAGE} sh -c 'ROOT=/data/user/0/com.xzielapp/files/rootfs; echo PID=\$(cat \$ROOT/tmp/xziel-wineserver-fg.pid 2>/dev/null); ps -A | grep -E \"box64|wineserver\" || true; find \$ROOT/tmp -maxdepth 3 -type s -print 2>/dev/null | sort'" \
        > "$OUT/wineserver-fg-after-warmup.txt" 2>&1 || true

      echo "XZIEL_X86BRIDGE_PRESTARTED_WINESERVER_STATE"
      cat "$OUT/wineserver-fg-state.txt" || true
      echo "XZIEL_X86BRIDGE_PRESTARTED_WINESERVER_CMD"
      tail -n 1200 "$OUT/wine-with-prestarted-server.txt" || true
      if grep -q 'XZIEL_PRESTARTED_CMD_STATUS=0' "$OUT/wine-with-prestarted-server.txt"; then
        echo "XZIEL_X86BRIDGE_PRESTARTED_CMD_GREEN"
      else
        echo "XZIEL_X86BRIDGE_PRESTARTED_CMD_NOT_GREEN"
      fi
      echo "XZIEL_X86BRIDGE_PRESTARTED_WINESERVER_LOG"
      tail -n 2600 "$OUT/wineserver-fg.log" || true
      echo "XZIEL_X86BRIDGE_PRESTARTED_WINESERVER_AFTER_WARMUP"
      cat "$OUT/wineserver-fg-after-warmup.txt" || true
      echo "XZIEL_X86BRIDGE_PERSISTENT_WINESERVER_KEEPALIVE"
      fi

      echo "XZIEL_X86BRIDGE_FAST_RELAUNCH diag=${XZIEL_PRELAUNCH_DEEP_DIAG:-1}"
      adb logcat -c
      adb shell am start -W -n ${XZIEL_PACKAGE}/com.winlator.XzielBootActivity | tee "$OUT/am-restart-pie.txt"
      sleep 3
      last_marker="PIE_BOX64_RELAUNCH"
      continue
    fi

    # XServer setup clears rootfs/tmp. That invalidates the foreground
    # wineserver socket that made the prelaunch cmd.exe probe GREEN. Wine then
    # falls back to spawning wineserver -d, whose fork/daemon path crashes under
    # the Android x86->ARM bridge. Recreate a foreground wineserver *after* the
    # XServer environment is ready, then keep that exact server for all launch
    # isolation probes below.
    if [[ "$pie_retry" == "1" ]]; then
      echo "XZIEL_X86BRIDGE_POST_XSERVER_WINESERVER_BEGIN"
      adb shell "run-as ${XZIEL_PACKAGE} sh -c '
        ROOT=/data/user/0/com.xzielapp/files/rootfs
        rm -rf \$ROOT/tmp/.wine-* 2>/dev/null || true
        rm -f \$ROOT/tmp/xziel-wineserver-postx.log \$ROOT/tmp/xziel-wineserver-postx.pid
        HOME=\$ROOT/home/xuser \
        USER=xuser \
        TMPDIR=\$ROOT/tmp \
        PATH=\$ROOT/opt/wine/bin:\$ROOT/usr/local/bin:\$ROOT/usr/bin:/system/bin \
        BOX64_DYNAREC=0 \
        BOX64_NOBANNER=1 \
        BOX64_LOG=1 \
        BOX64_LD_LIBRARY_PATH=\$ROOT/lib/x86_64-linux-gnu \
        ANDROID_SYSVSHM_SERVER=\$ROOT/tmp/.sysvshm/SM0 \
        WINEPREFIX=\$ROOT/home/xuser/.wine \
        WINEESYNC=0 \
        WINEFSYNC=0 \
        \$ROOT/usr/local/bin/box64 \$ROOT/opt/wine/bin/wineserver -f \
          > \$ROOT/tmp/xziel-wineserver-postx.log 2>&1 &
        echo \$! > \$ROOT/tmp/xziel-wineserver-postx.pid
      '" > "$OUT/wineserver-postx-start.txt" 2>&1 || true
      sleep 2
      adb shell "run-as ${XZIEL_PACKAGE} sh -c '
        ROOT=/data/user/0/com.xzielapp/files/rootfs
        echo PID=\$(cat \$ROOT/tmp/xziel-wineserver-postx.pid 2>/dev/null)
        ps -A | grep -E "box64|wineserver" || true
        find \$ROOT/tmp -maxdepth 3 -type s -print 2>/dev/null | sort
      '" > "$OUT/wineserver-postx-state.txt" 2>&1 || true
      adb exec-out run-as ${XZIEL_PACKAGE} cat files/rootfs/tmp/xziel-wineserver-postx.log \
        > "$OUT/wineserver-postx.log" 2>/dev/null || true
      echo "XZIEL_X86BRIDGE_POST_XSERVER_WINESERVER_STATE"
      cat "$OUT/wineserver-postx-state.txt" || true
      echo "XZIEL_X86BRIDGE_POST_XSERVER_WINESERVER_LOG"
      tail -n 400 "$OUT/wineserver-postx.log" || true

      timeout 30s adb shell "run-as ${XZIEL_PACKAGE} sh -c '
        ROOT=/data/user/0/com.xzielapp/files/rootfs
        HOME=\$ROOT/home/xuser USER=xuser TMPDIR=\$ROOT/tmp \
        PATH=\$ROOT/opt/wine/bin:\$ROOT/usr/local/bin:\$ROOT/usr/bin:/system/bin \
        BOX64_DYNAREC=0 BOX64_NOBANNER=1 BOX64_LOG=1 \
        BOX64_LD_LIBRARY_PATH=\$ROOT/lib/x86_64-linux-gnu \
        ANDROID_SYSVSHM_SERVER=\$ROOT/tmp/.sysvshm/SM0 \
        WINEPREFIX=\$ROOT/home/xuser/.wine WINEESYNC=0 WINEFSYNC=0 \
        \$ROOT/usr/local/bin/box64 \$ROOT/opt/wine/bin/wine C:\\\\windows\\\\system32\\\\cmd.exe /c ver
        rc=\$?
        echo XZIEL_POST_XSERVER_CMD_STATUS=\$rc
        exit \$rc
      '" > "$OUT/postxserver-cmd.txt" 2>&1 || true
      tail -n 300 "$OUT/postxserver-cmd.txt" || true
      if grep -q 'XZIEL_POST_XSERVER_CMD_STATUS=0' "$OUT/postxserver-cmd.txt"; then
        echo "XZIEL_X86BRIDGE_POST_XSERVER_CMD_GREEN"
      else
        echo "XZIEL_X86BRIDGE_POST_XSERVER_CMD_NOT_GREEN"
      fi
      echo "XZIEL_X86BRIDGE_POST_XSERVER_WINESERVER_READY"
    fi

    # If the Bionic PIE retry itself exited, reproduce the exact Wine/X11
    # launch while XServer, VirGL and ALSA are still alive. Turn on Box64 and
    # Wine loader/server diagnostics only for this bounded CI probe.
    if [[ "$pie_retry" == "1" ]]; then
      echo "XZIEL_X86BRIDGE_FULL_LAUNCH_PROBE_BEGIN"
      timeout 20s adb shell "run-as ${XZIEL_PACKAGE} sh -c '
        ROOT=/data/user/0/com.xzielapp/files/rootfs
        export HOME=\$ROOT/home/xuser
        export USER=xuser
        export TMPDIR=\$ROOT/tmp
        export DISPLAY=:0
        export WINEPREFIX=\$ROOT/home/xuser/.wine
        export PATH=\$ROOT/opt/wine/bin:\$ROOT/usr/local/bin:\$ROOT/usr/bin:/system/bin
        export BOX64_LOG=2
        export BOX64_DLSYM_ERROR=1
        export BOX64_LD_LIBRARY_PATH=\$ROOT/lib/x86_64-linux-gnu
        export ANDROID_SYSVSHM_SERVER=\$ROOT/tmp/.sysvshm/SM0
        export ANDROID_ALSA_SERVER=\$ROOT/tmp/.sound/AS0
        export VIRGL_SERVER_PATH=\$ROOT/tmp/.virgl/V0
        export GALLIUM_DRIVER=virpipe
        export WINEESYNC=0
        export WINEFSYNC=0
        export WINEDEBUG=+server,+process,+module,+loaddll
        timeout 8 \$ROOT/usr/local/bin/box64 \$ROOT/opt/wine/bin/wine explorer /desktop=nogui,1280x720 C:\\\\windows\\\\winhandler.exe /dir C:\\\\XZIEL \"Nacht-Chronicles-XZIEL.exe\"
      '" > "$OUT/full-launch-direct-probe.txt" 2>&1 || true
      echo "XZIEL_X86BRIDGE_FULL_LAUNCH_PROBE_OUTPUT"
      tail -n 1400 "$OUT/full-launch-direct-probe.txt" || true
      echo "XZIEL_X86BRIDGE_FULL_LAUNCH_PROBE_END"
    fi

    if [[ "$pie_retry" == "1" ]]; then
      # The Android XServer activity is deliberately kept alive after guest
      # termination on x86. Re-run the Windows-side startup under the same
      # prefix/display while forcing Box64/Wine diagnostics so an otherwise
      # silent status=1 cannot hide the failing layer.
      cat > "$OUT/xziel-exact-launch-probe.sh" <<'EOF'
ROOT=/data/user/0/com.xzielapp/files/rootfs
export HOME="$ROOT/home/xuser"
export USER=xuser
export TMPDIR="$ROOT/tmp"
export DISPLAY=:0
export PATH="$ROOT/opt/wine/bin:$ROOT/usr/local/bin:$ROOT/usr/bin:/system/bin"
export BOX64_LD_LIBRARY_PATH="$ROOT/lib/x86_64-linux-gnu"
export BOX64_LOG=2
export BOX64_DLSYM_ERROR=1
export BOX64_SHOWSEGV=1
export WINEPREFIX="$ROOT/home/xuser/.wine"
export WINEESYNC=0
        export WINEFSYNC=0
export WINEDEBUG=+process,+server,+module,+seh
export ANDROID_SYSVSHM_SERVER="$ROOT/tmp/.sysvshm/SM0"
export ANDROID_ALSA_SERVER="$ROOT/tmp/.sound/AS0"
export ANDROID_ASERVER_USE_SHM=true
export MESA_DEBUG=silent
export MESA_NO_ERROR=1
cd "$ROOT"

echo XZIEL_EXACT_PROBE_CMD_BEGIN
timeout 15 "$ROOT/usr/local/bin/box64" "$ROOT/opt/wine/bin/wine" 'C:\windows\system32\cmd.exe' /c ver
echo "XZIEL_EXACT_PROBE_CMD_STATUS=$?"
echo XZIEL_EXACT_PROBE_CMD_END

echo XZIEL_EXACT_PROBE_WINHANDLER_BEGIN
timeout 18 "$ROOT/usr/local/bin/box64" "$ROOT/opt/wine/bin/wine" 'C:\windows\winhandler.exe' /dir 'C:\XZIEL' 'Nacht-Chronicles-XZIEL.exe'
echo "XZIEL_EXACT_PROBE_WINHANDLER_STATUS=$?"
echo XZIEL_EXACT_PROBE_WINHANDLER_END

echo XZIEL_EXACT_PROBE_NACHT_DIRECT_BEGIN
# The one-file payload is ~888 MB and interpreter-only Box64 can spend well
# beyond 20s in PE/bootstrap I/O. Keep it alive long enough to distinguish a
# real bootstrap from the old immediate status=1 launcher failure.
timeout 90 "$ROOT/usr/local/bin/box64" "$ROOT/opt/wine/bin/wine" 'C:\XZIEL\Nacht-Chronicles-XZIEL.exe' &
nacht_probe_pid=$!
echo "XZIEL_NACHT_DIRECT_HOST_PID=$nacht_probe_pid"
elapsed=0
for step in 5 10 15 30 30; do
  sleep "$step"
  elapsed=$((elapsed + step))
  echo "XZIEL_NACHT_DIRECT_SAMPLE seconds=$elapsed"
  ps -A | grep -E 'box64|wine|wineserver|Nacht|winhandler' || true
  echo "XZIEL_NACHT_DIRECT_TMP_CENSUS seconds=$elapsed"
  find "$ROOT/tmp" "$ROOT/home/xuser/.wine/drive_c/XZIEL" -maxdepth 3 -type f -mmin -3 -print 2>/dev/null | head -n 120 || true
  kill -0 "$nacht_probe_pid" 2>/dev/null || break
done
wait "$nacht_probe_pid"
nacht_status=$?
echo "XZIEL_EXACT_PROBE_NACHT_DIRECT_STATUS=$nacht_status"
if [ "$nacht_status" = "124" ]; then
  echo XZIEL_NACHT_DIRECT_ALIVE_TO_TIMEOUT
fi
echo XZIEL_EXACT_PROBE_NACHT_DIRECT_END
EOF
      timeout 150s adb shell run-as ${XZIEL_PACKAGE} sh < "$OUT/xziel-exact-launch-probe.sh" \
        > "$OUT/exact-launch-probe.txt" 2>&1 || true
      adb exec-out screencap -p > "$OUT/nacht-direct-screen.png" 2>/dev/null || true
      echo "XZIEL_X86BRIDGE_EXACT_LAUNCH_PROBE"
      tail -n 5000 "$OUT/exact-launch-probe.txt" || true
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
adb exec-out run-as ${XZIEL_PACKAGE} cat files/rootfs/tmp/xziel-guest-output.log \
  > "$OUT/xziel-guest-output.log" 2>/dev/null || true
echo "XZIEL_X86BRIDGE_GUEST_FILE_CAPTURE_BEGIN"
tail -n 1200 "$OUT/xziel-guest-output.log" || true
echo "XZIEL_X86BRIDGE_GUEST_FILE_CAPTURE_END"

# Capture the in-APK persistent wineserver separately. APK27 starts this server
# immediately before direct Nacht launch, so this log distinguishes server
# startup failure from Wine/PE failure without relying only on logcat markers.
adb exec-out run-as ${XZIEL_PACKAGE} cat files/rootfs/tmp/xziel-wineserver-runtime.log \
  > "$OUT/xziel-wineserver-runtime.log" 2>/dev/null || true
echo "XZIEL_X86BRIDGE_RUNTIME_WINESERVER_CAPTURE_BEGIN"
tail -n 1600 "$OUT/xziel-wineserver-runtime.log" || true
echo "XZIEL_X86BRIDGE_RUNTIME_WINESERVER_CAPTURE_END"
adb shell "run-as ${XZIEL_PACKAGE} sh -c 'ROOT=/data/user/0/com.xzielapp/files/rootfs; echo XZIEL_RUNTIME_SOCKET_CENSUS; find \$ROOT/tmp -maxdepth 3 -type s -o -type f 2>/dev/null | grep -E "(server-|xziel-wineserver-runtime)" | sort | head -n 200; ps -A | grep -E "box64|wineserver|Nacht" || true'" \
  > "$OUT/runtime-wineserver-state.txt" 2>&1 || true
cat "$OUT/runtime-wineserver-state.txt" || true

# Snapshot NSIS self-extractor progress. Nacht-Chronicles-XZIEL.exe is an
# NSIS container; reaching ns*.tmp proves we are inside the one-file bootstrap.
# Presence/growth of game/7z.exe, xziel-nacht-vfs.zip, Xziel-Nacht.exe or
# scene.xzsc tells us exactly how far extraction has progressed.
adb shell "run-as ${XZIEL_PACKAGE} sh -c '
  ROOT=/data/user/0/com.xzielapp/files/rootfs
  TEMP=\$ROOT/home/xuser/.wine/drive_c/users/xuser/AppData/Local/Temp
  echo XZIEL_NSIS_TEMP_CENSUS
  find \$TEMP -maxdepth 3 -type f -printf "%s %p\\n" 2>/dev/null | sort -nr | head -n 200
  echo XZIEL_NSIS_DIR_CENSUS
  find \$TEMP -maxdepth 3 -type d -print 2>/dev/null | sort | head -n 200
  echo XZIEL_NSIS_PAYLOAD_MARKERS
  find \$TEMP -maxdepth 6 \\( -iname "7z.exe" -o -iname "xziel-nacht-vfs.zip" -o -iname "Xziel-Nacht.exe" -o -iname "scene.xzsc" \\) -print 2>/dev/null | sort
  echo XZIEL_RUNTIME_PROCESS_CENSUS
  ps -A | grep -E "box64|wine|wineserver|Nacht|7z|Xziel" || true
'" > "$OUT/nsis-runtime-state.txt" 2>&1 || true
cat "$OUT/nsis-runtime-state.txt" || true

adb shell "run-as ${XZIEL_PACKAGE} sh -c 'ls -la files/rootfs/tmp files/rootfs/tmp/shm 2>&1; find files/rootfs/tmp/shm -maxdepth 1 -type f -ls 2>/dev/null | head -n 200'" \
  > "$OUT/shm-state.txt" 2>&1 || true
echo "XZIEL_X86BRIDGE_SHM_STATE"
cat "$OUT/shm-state.txt" || true

adb shell ps -A | grep -E 'xziel|winlator|box64|wine|Nacht|7z|Xziel' | tee "$OUT/processes.txt" || true
adb shell dumpsys activity activities   | grep -E "mResumedActivity|topResumedActivity|${XZIEL_PACKAGE}"   | tee "$OUT/activity-final.txt" || true

adb exec-out run-as ${XZIEL_PACKAGE} cat files/rootfs/tmp/xziel-guest-output.log \
  > "$OUT/guest-output.txt" 2>/dev/null || true
if [[ -s "$OUT/guest-output.txt" ]]; then
  echo "XZIEL_X86BRIDGE_GUEST_OUTPUT_CAPTURED bytes=$(wc -c < "$OUT/guest-output.txt")"
  tail -n 500 "$OUT/guest-output.txt" || true
else
  echo "XZIEL_X86BRIDGE_GUEST_OUTPUT_EMPTY"
fi

# Preserve the guest stdout/stderr file written by the APK's ProcessHelper.
# This is the authoritative Wine/Box64 error stream for x86-bridge runs.
adb exec-out run-as ${XZIEL_PACKAGE} cat files/rootfs/tmp/xziel-guest-output.log \
  > "$OUT/xziel-guest-output.log" 2>/dev/null || true
if [[ -s "$OUT/xziel-guest-output.log" ]]; then
  echo "XZIEL_X86BRIDGE_GUEST_OUTPUT_CAPTURED bytes=$(wc -c < "$OUT/xziel-guest-output.log")"
  tail -n 300 "$OUT/xziel-guest-output.log" || true
else
  echo "XZIEL_X86BRIDGE_GUEST_OUTPUT_EMPTY"
fi

adb shell "run-as ${XZIEL_PACKAGE} sh -c 'find files/rootfs -type f \\( -name \"ld-linux-x86-64.so.2\" -o -name \"ld-linux*.so*\" -o -path \"*/bin/wine\" -o -path \"*/bin/wine64\" \\) -print 2>/dev/null | sort'" \
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

adb shell "run-as ${XZIEL_PACKAGE} sh -c 'if [ -d files/rootfs/tmp/shm ]; then ls -la files/rootfs/tmp/shm; fi'" \
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
