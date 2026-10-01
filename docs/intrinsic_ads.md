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
