# Church V1 — Limits and Runtime Plan

Status: engineering authority for the Church V1 prototype.
Last research pass: 2026-10-01.

This document separates external platform/measurement requirements from
current XZIEL implementation limits. A current engine limit is not treated as
an industry requirement, and an industry guideline is not silently promoted
to a hard platform limit.

## 1. Shipping targets

- Android target: API 36. The current XZIEL app already uses targetSdk 36 and
  compileSdk 36.1, satisfying the Google Play requirement effective
  2026-08-31 for new apps and updates.
- Main gameplay target: 60 FPS on capable mobile devices.
- Absolute design floor: 30 FPS. Optional 90/120 FPS may be exposed when the
  display/device and runtime policy can sustain it.
- Ad presentation must degrade before core combat simulation. Video creative
  updates, optional ad animation, ad cache residency, optional particles,
  shadows and secondary visual effects are lower priority than player input,
  zombie movement/attacks and weapon feedback.

## 2. Church authored geometry

Current Church V1 art targets:
- 180,000 minimum authored triangles
- 450,000 preferred authored triangles
- 900,000 authored-triangle ceiling for the current map target
- 2K maximum authored texture dimension in the current spec

These are project budgets, not Vulkan hard limits.

Runtime mesh rule:
- No XZSM batch may exceed 65,535 unique vertices when using 16-bit indices.
- The existing XZSM exporter uses <=18,000 triangles per batch, keeping even
  the worst raw 3-vertices-per-triangle case below that vertex-index ceiling.
- Do not lower the whole church's polygon count merely to satisfy mobile.
  Prefer spatial batching, frustum/portal/occlusion culling, streaming and LOD
  on distant/non-silhouette detail.
- Micro-triangle cleanup is allowed only when validated against source
  fidelity. Architectural silhouettes, altar detail, piers, windows and
  close-player surfaces are protected.

Transparency:
- Stained glass, fog and alpha effects are potentially overdraw-heavy.
- Do not stack decorative translucent layers without profiling.
- When GPU-bound, reduce fog/transparency work before deleting authored
  architectural detail.

## 3. Texture compatibility

Prototype:
- ASTC KTX2 is the current native XZIEL runtime texture path.

Shipping compatibility:
- ASTC is the preferred high-quality mobile format.
- ETC2 is required as the broad-compatibility fallback before a wide Android
  release.
- Use Play texture-compression targeting / asset packs rather than runtime
  decompression to RGBA where practical.
- Do not hand-author KTX2 containers. Use the Khronos KTX toolchain or another
  validated ASTC/ETC2 encoder.

The current 2K texture ceiling is below Vulkan's mandatory minimum 2D image
dimension capability of 4096 and therefore is not itself a platform problem.

## 4. Memory and thermal behavior

Android 17 introduces stricter per-app memory enforcement that varies with
device RAM. XZIEL must treat memory pressure as a runtime signal rather than
assuming one universal MB ceiling.

Priority under pressure:
1. Preserve gameplay state, collision, input and zombie combat simulation.
2. Drop/freeze video-ad decode and optional ad creative caches.
3. Reduce optional particles, shadows, reflection/fog work.
4. Stream/release distant map resources.
5. Never solve memory pressure by corrupting or deleting authoritative map
   geometry at build time.

Thermal:
- Continue using cached ADPF/Thermal state.
- Avoid high-frequency thermal polling.
- If thermally constrained, freeze the in-world TV to a static frame before
  reducing gameplay simulation quality.

## 5. Zombies map topology

Church V1 currently defines seven macro zones:
- spawn_chapel
- main_nave
- sacristy
- graveyard
- utility_basement
- crypt
- bell_tower

Gameplay anchor targets:
- 4 player spawns
- 12 zombie-window targets
- 7 door targets
- 6 wall-buy targets
- 4 Mystery Box anchors

Design rule:
- Treat nave bays, side aisles and attached spaces as spawn/visibility zones.
- Do not spawn zombies uniformly around the player.
- Exterior horde points route toward authored windows/barricades.
- Opening a door changes the set of eligible spawn zones and navigation paths.
- Piers and side-aisle architecture should break long sightlines rather than
  leaving the entire nave as one unobstructed training rectangle.

## 6. Current XZIEL horde limit — blocker, not design target

Current engine implementation:
- kMaxHordeZombies = 16 hard slots
- HordeConfig default maxActive = 8
- 32 authored spawn-point slots
- 256 navigation floors
- 256 static navigation obstacles
- 64 dynamic blockers
- 96 navigation links per floor

The 16-slot hard cap is currently the largest gameplay-capacity mismatch for a
four-player Zombies-style release. It must be stress-tested and redesigned
before Church V1 late-game balance is frozen.

Do not blindly copy a historical Call of Duty active-zombie count. The next
gate is to benchmark 16/24/32+ simulated actors on target Android tiers while
using CrowdBudgetPlanner to reduce distant animation, perception cadence,
ragdolls and shadows without reducing gameplay movement/attack simulation.

## 7. Intrinsic visual ads

Measurement baseline:
- >=50% of creative area visibly exposed
- visible portion >=1.5% of total screen area
- surface angle no more oblique than 55 degrees
- display/static: >=1 continuous second
- video/dynamic: >=2 continuous seconds
- one counted viewable impression per creative/user session by default

A fully downloaded asset is not an impression by itself.
Leaving and re-entering a placement does not create another viewable
impression for the same creative/session.

Church visual placements:
- 3 framed image placements on opaque stone piers
- 1 poster on the left reredos panel
- 1 TV/video placement on the right reredos panel

Disclosure:
- Do not disguise a paid creative as sacred artwork.
- If the commercial nature is not already obvious from the creative, provide a
  clear integrated "Ad" or "Advertisement" cue near/on the placement.
- Default visual placements are non-clickable. Any future click mechanic must
  be deliberate and protected from accidental combat taps.

## 8. Radio/audio advertising

Church radio policy:
- proximity alone never starts advertising audio
- explicit player interaction is required
- <=30 s creative duration
- ~15 s preferred duration
- audible advertising disclosure required from production creative/provider
- one counted ad exposure per session in the current Church prototype
- advertisement voices never steal weapon/zombie/UI voices
- gameplay may reclaim an advertisement voice when voice capacity is full

The engine's audible-exposure event is an internal metric until the selected
provider defines its billable audio event.

## 9. In-world TV/video — current blocker

Current state:
- The KTX2 bridge can replace the TV with a static creative.
- It does NOT yet decode/play a real video stream.

Target Android path:
1. H.264 MP4 compatibility baseline; 720p/30fps is sufficient for the current
   small in-world TV.
2. Hardware decode with Android MediaCodec/NDK.
3. Decoder output through an image/surface queue.
4. AHardwareBuffer-backed image with GPU sampled usage.
5. Import/sample the buffer in Vulkan through
   VK_ANDROID_external_memory_android_hardware_buffer.
6. Avoid CPU frame decode/copy in the render loop.
7. Fall back to a static KTX2 creative if decoder/import support is absent or
   runtime thermal/performance policy says to freeze video.

## 10. Store, privacy and traffic constraints

Google Play:
- Current targetSdk 36 is valid for the 2026 submission requirement.
- Avoid disruptive gameplay interstitials; Church V1 uses non-HUD diegetic
  placements.
- Never design placements to cause accidental taps.

Traffic:
- Developer/self-testing must use LocalAdProvider, provider test mode or demo
  ads.
- Repeated live impressions/clicks from the publisher or a small number of
  users must not be used to manufacture revenue.
- Production revenue and fill are never assumed or guaranteed.

iOS future port:
- Ads must match the app age rating.
- Provide in-app access to targeting information and a way to report
  inappropriate/age-inappropriate ads.
- If a provider performs cross-company tracking, ATT authorization is required
  before tracking/IDFA access.
- Contextual/non-tracking inventory should remain a supported path.

## 11. Immediate gates before ads are considered runtime-complete

1. Church placement close-ups must pass visual review after current refit.
2. Latest Church XZAD build must pass semantic path validation.
3. Engine + Android APK must remain green after IAB/audio-policy changes.
4. Add clear visual disclosure treatment to frame/poster/TV placements.
5. Wire XZAD loading into the actual Android/game map loop.
6. Feed real camera/frustum/occlusion/coverage data into AdSurface measurement.
7. Wire the radio's explicit interaction into AdAudioEmitter userInitiated.
8. Add official-toolchain mock KTX2 assets.
9. Implement or explicitly defer the zero-copy hardware video path.
10. Stress-test zombie capacity tiers before freezing Church V1 late-game
    spawns and room economy.

## Research authorities

External guidance used in this pass:
- IAB/MRC In-Game Advertising Measurement Guidelines 2.0
- IAB 2025 Gaming Measurement Framework
- IAB Creative Guidelines & Best Practices: Advertising in Gaming
- FTC Native Advertising: A Guide for Businesses
- Google Play target API and advertising/invalid-traffic policies
- Android game optimization, texture compression, memory, thermal and Vulkan
  documentation
- Khronos Vulkan/KTX specifications and tools
- Apple App Review Guidelines and App Tracking Transparency
- NZ:P official mapping documentation for zoning, barricades and four-player
  spawn structure

These references inform the design but do not replace a production ad
provider's contract, measurement certification or store review.
