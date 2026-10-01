# XZIEL intrinsic in-game ads v1

This module provides engine-owned placements for diegetic advertising without HUD popups.

## Placement types

- `AdSurface`: a mesh/material slot that can display an image or video creative.
- `AdAudioEmitter`: a spatial audio source such as a radio or television.

The engine owns placement state and measurement. The provider only supplies creatives and receives measurement events through `IAdProvider`.

## Threading contract

Provider requests and asset downloads must run outside render/audio callbacks. `primeAll()`, `primeSurface()`, `primeAudioEmitter()`, and refresh calls are intended for the game/update thread or a provider-owned async cache. Per-frame `stepSurface()` and `stepAudioEmitter()` perform fixed-capacity state updates and do not allocate.

## Measurement rules

A surface impression is only emitted after continuous qualifying visibility. A frame that is out of frustum, occluded, too distant, facing away, or below minimum screen coverage resets the continuous visibility timer.

An audio impression is only emitted after continuous audible playback inside the emitter radius. Audio ads are represented as `AudioSourceKind::Advertisement`, intentionally below weapons, zombie voices, UI, music, and core ambience in the audio voice priority model.

Cooldowns and per-session impression caps are enforced in engine state. Repeated movement through a trigger does not automatically create repeated impressions. A placement must explicitly refresh after cooldown.

## Offline testing

`LocalAdProvider` maps placement IDs to local engine asset IDs and is suitable for church-map development without network access.

Set `XZIEL_AD_DEBUG=1` to enable the debug-mode switch. Runtime UI/logging can consume `surfaceDebugSnapshot()` and `audioDebugSnapshot()`.

No automatic clicks are generated and no impression is emitted merely because a creative was downloaded.


## Runtime texture bridge

The Android Vulkan static-mesh renderer exposes `queueRuntimeTextureReplacement()` for `AdSurface` creatives. A placement uses a dedicated placeholder texture asset, and a packaged ASTC KTX2 creative can replace that texture at runtime. The existing two-frame Vulkan descriptor swap path is reused so the creative is never rebound into a descriptor set that is still in flight.

The replacement path is intentionally game-thread initiated. Asset I/O is bounded to 64 MiB, GPU upload is fence-driven, and descriptor swaps complete inside the normal renderer record/service path. Runtime replacement is independent of the Sanctum streaming graph, so Church V1 and other non-Sanctum maps can use the same mechanism.

Each ad placement should use a unique placeholder texture when independent creative rotation is required. Sharing the same placeholder texture intentionally shares the replacement across every material bound to that texture.


`VulkanClearRenderer` exposes the map-level bridge as `queueIntrinsicAdSurfaceCreative(source, replacement)`. The game loop therefore does not need to access `VulkanStaticMeshRenderer` or Vulkan descriptor state directly.


## Android radio audio bridge

`AndroidAudioEngine` can preload a PCM16 WAV creative on the game thread with `prepareAdvertisement()`, start it with `playAdvertisement()`, and update gain/pan atomically with `updateAdvertisementSpatial()`. The AAudio callback performs no file I/O and allocates nothing. Creative replacement is rejected while an ad voice is queued or playing, avoiding races with the callback. Gameplay cues retain their existing centered mix; spatial panning is applied only to the advertisement voice. Stopping or voice-stealing an ad releases the in-flight state.


## XZAD map sidecar

Intrinsic placement metadata is not entrusted to renderer/importer-specific GLB extras. `XZAD` v1 is a compact little-endian sidecar parsed by `parseIntrinsicAdMapXzad()` into fixed-capacity arrays. Surface records carry the bound placeholder texture path, world-space center/normal, physical dimensions, viewability thresholds, cooldown/cap, and image/video flags. Audio records carry emitter position, fallback audio path, attenuation range, gain, listen threshold, cooldown, and cap. Duplicate IDs, malformed paths, invalid ranges, unknown flags, truncation, and trailing bytes are rejected.
