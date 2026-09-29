# XZWin World at War EXE probe

This branch is an isolated compatibility experiment. It does **not** replace
XZIEL's native ARM64/Vulkan path.

## First public test target

- Custom map: **MW2 Rust Zombies**
- Version: **1.0 / 1.01 family**
- Author: **Psh**
- Distribution form: Windows `.exe` installer
- Community catalog: CallOfDutyRepo
- Reason for choosing it: the map page explicitly says it does not require T4M,
  which removes one extra dependency from the first compatibility test.

The executable is an installer for a World at War custom map. It is not a
self-contained Call of Duty engine. The important first question is whether
Wine can execute the installer and expose its `.ff` / `.iwd` payload.

XZIEL does not vendor the commercial World at War game, commercial DLLs, or
this community map binary in git. The CI probe downloads the public installer
only for the duration of the job and uploads metadata/reports, not the map.

## Gates

1. **PE gate** — confirm the downloaded file is a valid Windows PE executable.
2. **Archive census** — inspect embedded members when the installer format is
   readable by 7-Zip.
3. **Wine installer gate** — run the installer in an isolated Wine prefix and
   census files created by it.
4. **Android host compile gate** — compile XZIEL targetSdk 35 with the
   experimental `XzWinRuntime`.
5. **ARM64 device gate** — bundle a compatible Box64 host + Wine/rootfs and run
   the same installer on Android.
6. **XZIEL import gate** — translate the installed WaW payload into XZIEL-owned
   runtime formats instead of requiring `CoDWaW.exe`.

## targetSdk 35 constraint

Android apps targeting API 29+ cannot rely on directly executing arbitrary
files placed in their writable app home. Therefore the experimental host
expects the ARM64 Box64 launcher to be packaged in the APK native-library
directory as `libxzbox64.so`. Wine/x86_64 remains guest content under the
private XZWin rootfs and is opened by Box64.

Expected private layout:

```text
files/
  xzwin/
    rootfs/
      opt/wine/bin/wine64
      usr/...
      lib/...
    prefix/default/
    imports/
    logs/
```

The native XZIEL path remains:

```text
libxziel.so -> ARM64 -> Vulkan -> Android
```

The experimental compatibility path is:

```text
APK-native Box64 host -> Wine64 guest -> map-installer.exe
```

No Winlator UI, desktop, container chooser, or branding is part of this
experiment. License notices/source obligations for reused open-source
components still apply.
