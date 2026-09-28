# GTA Chinatown Wars Android 3D Mod Lab

## Project isolation

This is a standalone for-fun modding project. It must not depend on, import,
or modify Nacht/XZIEL/ZOMBIESSSSSSS PORTABLE code, assets, workflows, runtime
profiles, or engine assumptions. Shared repository hosting is organizational
only; CTW work stays inside this branch/path and has its own CI gates.


Experimental, clean-room modding workspace for **GTA: Chinatown Wars Android**.

This project does **not** contain Rockstar game data. Bring a legally obtained APK/game install.

## Target

Primary reverse-engineering target:

- Android ARM64 build 4.4.243 when available
- `assets/game.pak`
- `assets/dxt.bin`
- `lib/arm64-v8a/libGame.so`
- `lib/arm64-v8a/libopenal.so`

## Goals

1. Reproduce the PSP Fusion Fix-style 3D / third-person camera on Android.
2. Add a first-person camera mode.
3. Fix player/body/weapon clipping and render-mask issues exposed by low/first-person cameras.
4. Increase visible world distance without near-camera world pop-in.
5. Treat draw distance as a full pipeline problem: far clip + sector visibility + streaming radius + LOD/culling.

## Public reverse-engineering references

- DK22Pac / CTW-Mobile-Explorer — Android `game.pak` resource format.
- ThirteenAG / WidescreenFixesPack — CTW PPSSPP Fusion Fix camera implementation.
- NaGaa95 / gtactw_nx — ARM64 Android `libGame.so` loading/hooking reference.
- spicybung / BLeeds — Blender tooling for Leeds Engine model/world formats.

These projects remain under their respective licenses.

## Phase gates

### Gate A — APK + PAK inventory
`tools/gtactw/ctw_probe.py`:

- confirms the expected ARM64 game/runtime files;
- parses the 24-byte PAK header;
- reads the split 16-bit resource-offset table exactly as documented by CTW-Mobile-Explorer;
- computes logical resource offsets;
- emits JSON suitable for CI logs.

### Gate B — Android symbol/pattern map
Infrastructure is now in place via `tools/gtactw/elf_probe.py`:

- validates ELF64 little-endian AArch64;
- fingerprints the full binary and `.text`;
- extracts GNU build-id when present;
- enumerates static/dynamic symbols;
- verifies known `GameNative` JNI exports;
- groups camera, streaming, LOD/culling and player-render candidates from symbols and strings.

The real Android addresses are intentionally not guessed. They are populated only after probing the user's own `libGame.so`.

### Gate C — 3D camera
Port the behavior of the PSP camera mod without copying PSP addresses. Android symbols/patterns must be found independently.

### Gate D — full-body / near-clip repair
Locate player visibility masks, model-part culling and near-clip behavior.

### Gate E — extended world distance
Patch/parameterize far clip, sector visibility, streaming radius and LOD thresholds together.

## Usage

Inspect an APK without extracting copyrighted assets:

```bash
python tools/gtactw/ctw_probe.py path/to/GTACW.apk
```

Extract only the required files from **your own APK** into a local work directory:

```bash
python tools/gtactw/ctw_probe.py path/to/GTACW.apk --extract ./local_ctw
```

The local extraction directory must not be committed.

Inventory the complete local PAK without dumping it into Git:

```bash
python tools/gtactw/pak_inventory.py ./local_ctw/assets/game.pak --manifest ./local_ctw/pak_manifest.json
```

Extract only selected resource IDs:

```bash
python tools/gtactw/pak_inventory.py ./local_ctw/assets/game.pak --extract ./local_ctw/resources --ids 12,42,900
```

Fingerprint/map the Android runtime:

```bash
python tools/gtactw/elf_probe.py ./local_ctw/lib/arm64-v8a/libGame.so --out ./local_ctw/libGame_report.json --require-jni
```

Patch goals and required gates are machine-readable in `android_patch_targets.json`.


## Native proxy loader

The Android mod uses a separate native proxy instead of permanently editing the
Rockstar binary:

- the original `libGame.so` becomes `libGame_orig.so`;
- CTW3D builds a new proxy named `libGame.so`;
- every known `GameNative` JNI entry is forwarded to the original library;
- right-stick state is captured for the custom camera;
- right-stick click (Android gamepad code 13) cycles stock / third-person /
  first-person camera state while still forwarding the button to the game;
- internal patches are refused unless the runtime build matches a verified
  profile.

The local APK repacker is:

```bash
python tools/gtactw/apk_modpack.py GTACW.apk \
  --loader-so path/to/libGame.so \
  --out GTACW-3D-unsigned.apk
```

Then use Android build-tools to align and sign the local APK:

```bash
zipalign -P 16 -f 4 GTACW-3D-unsigned.apk GTACW-3D-aligned.apk
apksigner sign --ks YOUR_KEYSTORE --out GTACW-3D.apk GTACW-3D-aligned.apk
apksigner verify --verbose GTACW-3D.apk
```

## Version-safe patch profiles

Generate a template from a real `libGame.so` report:

```bash
python tools/gtactw/profile_template.py \
  ./local_ctw/libGame_report.json \
  --out ./local_ctw/ctw-profile.json
```

The template intentionally leaves all six internal patch targets empty until
they are reverse-engineered and verified:

- `camera_update`
- `projection_setup`
- `world_stream_update`
- `sector_visibility`
- `lod_test`
- `player_render`

Once all six are verified, generate the native table:

```bash
python tools/gtactw/profile_emit_c.py \
  ./local_ctw/ctw-profile.json \
  --out projects/gtactw-android-3d/android-loader/ctw_profiles_generated.h
```

The runtime also compares stable JNI RVAs before accepting a profile, so
offsets from one CTW build are not silently applied to another build.


## World streaming census

After extracting or locating `game.pak`, build a metadata-only census of every
named CTW worldblock:

```bash
python tools/gtactw/world_census.py ./local_ctw/assets/game.pak --out ./local_ctw/world_census.json --require-clean
```

The census reports per-worldblock instance/level density, sector counts,
origins and local level bounds. This is intended to guide coordinated
stream-radius/LOD/far-clip tuning rather than blindly increasing a single
draw-distance constant.
