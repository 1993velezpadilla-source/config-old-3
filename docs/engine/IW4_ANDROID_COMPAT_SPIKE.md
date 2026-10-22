# IW4 Android compatibility spike

Status: experimental, isolated from the shipping Xziel/Xeno path.

## Goal

Answer one narrow engineering question before changing engine direction:

> Can a legally owned Call of Duty: Modern Warfare 2 (IW4) Windows runtime be made
> to execute on an ARM64 Android phone and load our Sanctum/church test content?

This spike does **not** replace Xziel Engine. It lives on a separate branch and
must not change the shipping APK or native Xziel renderer.

## What counts as success

The spike only passes when all of the following are demonstrated on a physical
ARM64 Android device:

1. the original user-supplied IW4 runtime starts through the compatibility host;
2. the process reaches the game renderer rather than only a launcher/menu shell;
3. IW4x or the selected public mod layer initializes successfully;
4. a custom usermap generated from Xziel church content starts;
5. the player can spawn, move, look, collide with the map, and remain alive for
   at least 60 seconds;
6. logs and one screenshot are captured;
7. no original MW2 executable, DLL, fastfile, IWD, texture, sound, model, or
   other proprietary game payload is committed to this repository or bundled
   into a redistributable Xziel APK.

A menu boot by itself is a FAIL.

## Important technical boundary

Public IW4x is a mod/client layer for the Windows MW2 runtime. It is not a
portable replacement for the underlying IW4 engine. The public IW4 tooling we
can use describes/modifies assets and hooks the PC game, but it does not provide
the complete Infinity Ward engine source required to simply cross-compile IW4
from x86/Win32/DirectX to Android/ARM64/Vulkan.

Therefore this spike has two distinct routes:

### Route A — original-runtime compatibility proof

Use a user-supplied, legally owned MW2 installation. Do not copy it into Git.

Run the original Windows executable on Android through a Windows/x86
compatibility stack. This proves whether the *actual* runtime can execute on the
phone. It is not a native Android port and is not the intended Google Play
shipping architecture.

### Current probe stack

First probe: **Winlator/Wine + Box86/Box64/DXVK** on Android. This is the fastest
way to answer the runtime question because it already targets Windows games on
Android and exposes per-game container settings.

Second probe if the first path is unstable: **Hangover/Wine WoW64** with its
x86-32-on-ARM64 emulator DLL path. Hangover is attractive for this specific
runtime because it can run i386 Windows applications on ARM64 without requiring
a traditional 32-bit Unix userspace.

These are probe environments only. We do not fork either into the shipping game
unless the experiment first proves IW4 itself is worth pursuing.

Expected render translation for the PC runtime is Direct3D 9 -> DXVK -> Vulkan
where the device/driver supports the required Vulkan feature set.

### Route B — church map bridge

Prepare our church as an IW4-compatible usermap.

The current church source is a high-detail GLB and is already split by the
Xziel exporter into bounded static batches. It must not be pushed into IW4 as
one giant XModel. The bridge should preserve that partitioning and create a
coarse collision/world shell plus static-model chunks.

Current source authority:

- `tools/church_map/export_xziel_original_clean.py`
- source GLB default: `church/source/st-giles-cripplegate.glb`
- Xziel native map/runtime output remains the authoritative Xziel path.

Public IW4 tooling can load/build a useful subset of XModel/material/weapon
assets, but public OpenAssetTools does not currently provide disk load support
for the full IW4 `GfxWorld`, `clipMap_t`, `GameWorld`, or `FxWorld`
types. So a complete church map needs the established custom-map toolchain, not
just OAT.

The existing IW4x map-porting path converts maps from IW3/Call of Duty 4 into
IW4 usermaps. For Sanctum, the practical bridge is therefore:

1. keep the original church GLB untouched;
2. create bounded static-model chunks from the same source partitioning already
   used by Xziel;
3. build a coarse authored collision/world shell suitable for the IW3/IW4 map
   pipeline;
4. place the church chunks as static models;
5. build/port the resulting test map into IW4;
6. launch it as `xziel_sanctum` on the compatibility runtime.

The final map build may require a locally installed, legally obtained game/tool
installation. CI must never download or cache proprietary game files.

## Why this branch exists

This is a feasibility gate, not a rewrite.

If Route A + Route B reach the physical-device acceptance criteria, we have
evidence that the original IW4 runtime can be used as a private reference/test
bed on Android.

If they do not, Xziel loses nothing: the current engine branch and APK stay
untouched.

## First automated gate

`tools/iw4_android_spike/prepare_owned_install.py` validates a local
user-provided MW2 installation and writes a machine-readable manifest. It:

- requires `iw4mp.exe`, `main/`, and `zone/`;
- verifies that `iw4mp.exe` is a Windows PE image;
- records the PE machine type and whether it is PE32 or PE32+;
- hashes only the executable for test identity;
- records whether IW4x and the Xziel church usermap are already present;
- never downloads, copies, uploads, or redistributes game data.

The manifest is deliberately safe to commit only if paths are sanitized. CI
tests use synthetic fixtures, never real game files.

## Next runtime gate

After a real owned installation is available to the device/host, the next
implementation step is an Android compatibility launcher that:

1. mounts the owned game directory read-only where possible;
2. starts the x86 Windows runtime through the chosen translation/Wine stack;
3. records stdout/Wine logs and process exit state;
4. injects no proprietary data into the APK;
5. launches the test usermap directly once the bridge exists.

Only after that gate works is it worth investing in full church conversion.
