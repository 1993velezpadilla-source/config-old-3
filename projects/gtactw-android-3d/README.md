# GTA Chinatown Wars Android 3D Mod Lab

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
Next: fingerprint `libGame.so`, exported JNI entry points, camera candidates, renderer/streamer candidates.

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
