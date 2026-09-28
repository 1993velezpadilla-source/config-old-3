# CTW Android 3D Mod

Mini-project for Grand Theft Auto: Chinatown Wars Android, targeting **4.4.243 / arm64-v8a**.

## Goals

- Keep the original Android game/runtime as the gameplay base.
- Add switchable **Classic / Third Person / First Person** camera modes.
- Fix near-camera player/weapon geometry that the original top-down camera never needed to render cleanly.
- Increase practical world visibility by addressing **camera far clip + world streaming radius + sector/LOD culling**, not merely the projection far plane.
- Preserve original missions, controls, audio, UI and gameplay.

## Public reverse-engineering references

This repository does **not** contain Rockstar game data.

- NaGaa95/gtactw_nx — native loader for CTW Android 4.4.243 arm64.
- DK22Pac/CTW-Mobile-Explorer — Android game.pak/resource format research.
- ThirteenAG/WidescreenFixesPack — GTACTW PPSSPP Fusion Fix with working third-person camera hooks.
- spicybung/BLeeds — Blender IO for Leeds Engine formats.

## Input layout

Run `tools/extract_owned_apk.py` against a legally obtained APK:

```
python tools/extract_owned_apk.py /path/to/gtactw.apk work/ctw
```

For 4.4.243 the extractor expects and copies:

- `assets/game.pak`
- `assets/dxt.bin`
- `lib/arm64-v8a/libGame.so`
- `lib/arm64-v8a/libopenal.so`

It also emits hashes and a manifest so every patch is tied to the exact binary revision.

## Phase gates

1. **INPUT_GREEN** — exact game files identified and hashed.
2. **PAK_GREEN** — game.pak header/resource table parses safely.
3. **CAMERA_GREEN** — third-person hook works without changing gameplay.
4. **PLAYER_RENDER_GREEN** — full player/weapon survives low/near camera.
5. **STREAMING_GREEN** — far geometry/LOD loads before entering view.
6. **ANDROID_GREEN** — patched package boots and completes an in-game smoke test.

The first implementation target is **non-destructive**: original files remain untouched and patched outputs are written under `out/`.
