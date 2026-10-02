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

## 3.1 Vulkan binding limits

Push-constant ceiling:
- Vulkan Core guarantees only 128 bytes of push constants.
- XZIEL StaticMeshRenderer already uses exactly 128 bytes and has a compile-time
  static_assert protecting that size.
- Do not add ad placement IDs, video frame state, creative metadata or any new
  per-material fields to the static-mesh push-constant block.
- Future intrinsic-ad/video metadata must use existing material/descriptor
  state or a separate uniform/storage buffer.

Descriptors:
- Vulkan Core guarantees at least 16 per-stage sampled images/samplers and at
  least 4 bound descriptor sets. Query the physical device for actual values.
- The current one-texture-per-material/draw model does not need one sampler
  binding for every Church placement simultaneously, so five intrinsic visual
  placements do not by themselves require bindless descriptors.
- Any future texture-array/bindless redesign must be feature/limit queried and
  must retain a portable fallback.

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

## 4.1 Church lighting budget

The current Blender Main Nave reference uses 23 authored light objects:
- 4 altar-candle point lights
- 8 chandelier-candle point lights
- 6 cold stained-glass/side area lights
- 4 warm central point fills
- 1 altar area key

These 23 lights are a look-development reference, not a runtime requirement.

XZIEL runtime budgets:
- Low: 3 dynamic / 1 shadowed
- Medium: 6 dynamic / 1 shadowed
- High: 12 dynamic / 3 shadowed
- Ultra: 24 dynamic / 6 shadowed

Runtime conversion target:
- candle flames use emissive geometry/lightmaps; never one dynamic light per candle
- the chandelier uses one clustered/fake practical light, not eight
- stained-glass color shafts should be baked/static where possible
- reserve shadowed dynamic lights for player/combat-critical lighting and at
  most one principal Church key on Medium
- Church V1's intended visual identity must remain readable with the Medium
  6/1 light budget; High adds refinement rather than making the scene work at
  all

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

## 5.1 Movement-space metrics

Current XZIEL character metrics:
- player collision radius: 0.28 m (0.56 m diameter)
- player collision height: 1.78 m
- player eye height: 1.62 m
- walk: 4.4 m/s
- sprint: 6.4 m/s
- tactical sprint: 7.2 m/s
- zombie half-width: 0.38 m (0.76 m body width)
- zombie body height: 1.86 m

Current Main Nave geometry:
- nave: ~18 m wide x 30 m long
- columns: x = +/-6.1 m
- bays/columns: ~4 m longitudinal spacing
- pew banks leave ~2.1 m central aisle
- side circulation between column envelope and wall is roughly 1.9-2.2 m

These values are currently compatible with first-person combat circulation. The
central aisle is approximately 3.75 player diameters wide and 2.75 zombie body
widths wide. Side aisles are intentionally tighter but remain wider than twice
the player diameter.

Do not widen the whole nave. Preserve tension through furniture, pier sightline
breaks, opened/closed doors and active spawn zones. Validate every critical
door/corridor against the actual XZIEL capsule rather than real-world
architecture alone.

At 7.2 m/s a player can cross the unobstructed 30 m nave in roughly 4.2 seconds.
Therefore long straight-line traversal must be interrupted by combat,
navigation, doors, pew banks or spawn pressure; raw room size alone will not
create difficulty.

## 5.2 Spawn-zone gap

Current XZIEL map capacities are adequate for Church V1:
- 32 zombie spawn points
- 32 zombie windows/barricades
- 16 doors
- 256 navigation floors
- 256 static map boxes/obstacles

However, the current map format sends all zombie spawn points to
HordeDirector as one global list. It has no authored spawn-zone/adjacency
concept and therefore cannot yet express the key Zombies rule that closed
doors and player-local zones constrain eligible spawns.

Before Church V1 expands beyond a single-room prototype, add:
- fixed-capacity spawn-zone AABBs
- spawn-point-to-zone membership
- zone adjacency
- per-zone activation/gating by door state
- player-position zone lookup
- eligible-spawn filtering before minimum-distance selection

The 30 m Main Nave should be logically segmented into at least south, middle
and apse spawn regions even if the rendered church remains one seamless room.
Decorative stained glass at ~4.85 m elevation is not a zombie ingress point.
Ground-level barricades/doors must be authored separately.

## 6. Current XZIEL horde limit — blocker, not design target

Current engine implementation:
- kMaxHordeZombies = 16 hard simulation slots
- HordeConfig default maxActive = 8
- Android prototype VulkanGameScene stores only 8 visible zombie states
- the current prototype renderer constructs each zombie from many per-body-part
  primitive draws; raising the visible array alone would multiply draw calls and
  is not the shipping scalability path
- 32 authored spawn-point slots
- 256 navigation floors
- 256 static navigation obstacles
- 64 dynamic blockers
- 96 navigation links per floor

The 8-visible / 16-simulated split is currently the largest gameplay-capacity
mismatch for a four-player Zombies-style release. It must be redesigned before
Church V1 late-game balance is frozen.

Do not raise the prototype visible-zombie array to 32 while retaining the
piecewise primitive renderer. The shipping path is a real zombie mesh/skeleton
path with GPU-friendly batching/instancing, then a stress matrix at 8/16/24/32
active actors on target Android tiers. CrowdBudgetPlanner should reduce distant
animation, perception cadence, ragdolls and shadows without reducing gameplay
movement/attack simulation.

Do not blindly copy a historical Call of Duty active-zombie count. Reserve
zombies can be queued outside the active set; the active set must be selected
from measured CPU/GPU budgets.

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
