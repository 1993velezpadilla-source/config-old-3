# COD Mobile → Xziel AAA-Mobile Clean-Room Engine Study

Research date: 2026-09-21  
Target: Xziel / NZ:P native Android stack  
Method: clean-room architecture reconstruction from public technical material, public build metadata, conference material, vendor case studies, and open-source technology.

> This document does **not** depend on copied Call of Duty: Mobile source code, ripped proprietary assets, leaked internal files, or bypassing anti-cheat. The purpose is to reproduce the engineering principles in an original implementation that Xziel can own, test, optimize, and ship.

---

## 1. Executive conclusion

Call of Duty: Mobile is not best understood as “a Unity game with expensive assets.”

Public technical evidence shows a much more useful architecture:

1. **Unity foundation, heavily extended by TiMi J3.**
2. **A scalable mobile rendering pipeline** rather than one fixed graphics path.
3. **Physically based rendering with several mathematical quality tiers.**
4. **Dynamic device/performance/thermal adaptation.**
5. **Texture streaming, atlasing, shader LOD and aggressive resource management.**
6. **GPU-assisted content production and baking.**
7. **Device-specific renderer paths including Vulkan on supported hardware.**
8. **Strong frame-pacing, shader-cache/prewarm and stutter control work.**
9. **A mature spatial-audio architecture.**
10. **Automated compatibility/performance validation across a large device matrix.**
11. **Segmented/down-loadable asset delivery rather than requiring every resource to be resident at launch.**
12. **Continuous optimization after release, including super-resolution, high-refresh modes, memory-leak work, particle prewarming and device-specific profiles.**

The lesson for Xziel is therefore not “copy Unity” and not “copy CODM.”

The lesson is to turn Vril into a **two-layer engine**:

```
AUTHORITATIVE GAMEPLAY
QuakeC / Vril simulation / zombie rules / weapons / collision / networking
        |
        | stable state + events
        v
MODERN PRESENTATION PLATFORM
renderer / materials / lighting / animation / VFX / audio / streaming /
device profiles / dynamic quality / frame pacing / telemetry
```

That separation lets us modernize visual quality without destroying the gameplay code already working.

---

## 2. What is publicly verified about COD Mobile

### 2.1 Unity foundation — high confidence

Activision stated publicly at launch that Call of Duty: Mobile was developed with Tencent/TiMi using Unity.

TiMi technical presentations later describe extensive engine modification and a custom technical pipeline rather than an untouched stock renderer.

Sources:

- Activision Call of Duty launch/development material:
  https://www.callofduty.com/
- Samsung Developer — Adaptive Performance in Call of Duty Mobile:
  https://developer.samsung.com/galaxy-gamedev/gamedev-blog/cod.html
- Unite Shanghai 2019 / TiMi J3 engine presentation transcript:
  https://www.gamersky.com/handbooksy/201907/1199672.shtml
- GameRes transcript:
  https://www.gameres.com/844463.html

### 2.2 Scalable HD rendering pipeline — high confidence

TiMi described a unified scalable rendering pipeline.

High-end path:
- HDR render target;
- higher-quality PBR;
- more complete lighting/shadow effects.

Lower-end path:
- no expensive conventional post stack;
- a OnePassHDR-style path;
- tonemapping approximated in the final shader.

This is critical: scalability is architectural, not an afterthought.

### 2.3 PBR tiers — high confidence

TiMi described four mathematical PBR approximation tiers plus compatibility handling.

Character rendering:
- full PBR information retained broadly across tiers;
- direct specular: GGX;
- direct diffuse: Lambert;
- specular GI: cubemap / IBL;
- diffuse GI: spherical-harmonic probes.

Static/environment rendering:
- shader LOD;
- shadowmask/lightmap strategies;
- reflection/IBL data;
- cheaper approximations on lower hardware.

Material packing publicly described included:
- albedo;
- normal + roughness;
- metallic + AO.

### 2.4 Engine-level content pipeline changes — high confidence

The public TiMi talk describes:
- custom hair/skin/character rendering;
- substantial terrain-system modification;
- Unity + Houdini workflow;
- draw-call merging;
- Vertex Fetch Texture;
- GPU light baking;
- automated/procedural probe placement;
- procedural vegetation preparation;
- Texture Atlas;
- Texture Streaming;
- PBR Shader LOD.

This matters as much as renderer code. AAA quality requires an industrialized asset pipeline.

### 2.5 Runtime adaptive performance — high confidence

Samsung publicly documented a technical collaboration with TiMi J3.

CODM dynamically reacted to:
- CPU frame time;
- GPU frame time;
- thermal state/trend;
- bottleneck type.

Documented quality variables included:
- shadow distance;
- foliage LOD;
- target framerate;
- animation LOD.

Samsung reported higher average FPS and lower device temperature during its case study.

Current Android equivalent for an original engine should be based on ADPF / Android thermal APIs rather than the deprecated legacy GameSDK path.

### 2.6 Modern Vulkan/device-specific paths — high confidence that they exist, exact internal implementation unknown

Public Samsung engineering material and later CODM optimization notes support renderer work beyond a generic GLES-only path. Later Chinese CODM releases document Vulkan expansion to additional GPU families, shader-cache work, high refresh rates and device-specific optimization.

We should copy the strategy, not implementation details:
- capability detection;
- backend selection;
- shader cache;
- backend-specific fast paths;
- safe fallback.

### 2.7 Spatial audio — high confidence

Audiokinetic/TiMi presentations describe Call of Duty: Mobile integration with Wwise Spatial Audio.

Public material discusses:
- mobile-specific ray-budget constraints;
- indoor/outdoor acoustic zones;
- reverb buses;
- early reflections;
- different room archetypes.

Source:
https://www.youtube.com/watch?v=QsIwq2DoFx4

### 2.8 IL2CPP / native-code protection — medium/high confidence

Public reverse-engineering projects specifically support CODM's modified IL2CPP metadata layouts and obfuscation.

This is useful to establish the runtime family, **not** as a source of code for Xziel.

Examples:
- https://github.com/rodroidmods/il2cpp-dumper-rs
- https://github.com/djkaty/Il2CppInspector
- https://github.com/tien0246/Il2CppDumper-for-COD

Exact current Unity editor/runtime version for the 2026 global Android release is **not treated as verified** in this study. Public sources conflict across historical releases, and the custom fork makes an editor version number much less important than the architecture.

---

## 3. What CODM appears to optimize continuously

Public update notes over several years reveal recurring priorities:

### Rendering / GPU
- Vulkan expansion by device/GPU family;
- shader compile/cache optimization;
- super-resolution;
- higher refresh rates;
- effects cost reduction;
- quality profiles by SoC/GPU;
- foldable/aspect-ratio support.

### CPU
- animation LOD;
- scene/update reduction;
- runtime quality scaling;
- less redundant work;
- big.LITTLE / scheduling-aware tuning in historical Tencent tooling.

### Memory
- reduced effects/animation memory;
- memory-leak fixes;
- removal of redundant resources;
- streaming/downloading content;
- unloading scene resources more aggressively.

### Stutter
- shader cache;
- shader prewarm;
- VFX/particle prewarm;
- scene loading/unloading fixes;
- background/pre-download pipelines.

### Thermal / power
- target-FPS adaptation;
- bottleneck detection;
- thermal-aware scaling;
- backend-specific power optimization.

### Network
Public notes mention traffic reduction, feedback/position precision work and redundant-update reduction. Exact client prediction, interpolation, lag compensation and server implementation details are not sufficiently verified publicly for this document, so Xziel should use established FPS networking engineering rather than pretending an unverified CODM implementation is known.

---

# 4. Current Xziel baseline

Current repo path inspected:

```
android/jni/src/Android.mk
```

Current renderer/runtime characteristics:

- Vril Engine;
- SDL2;
- GL4ES;
- GLES 2.0 / EGL;
- OpenSL ES linkage;
- SDL2_mixer;
- classic GLQUAKE renderer path;
- Android NDK;
- native arm64 target;
- existing touch/gyro work.

Current compile path includes:

```
-DGLQUAKE
-DPLATFORM_RENDERER=gl
-lGLESv2
-lEGL
```

The Android patch creates an OpenGL ES 2.0 context and uses GL4ES to support the legacy renderer.

This is a sensible portability bridge but it is **not** the renderer foundation we should expect to carry a modern AAA-mobile feature set forever.

Existing project work already follows one principle we want to retain:
presentation features such as visual weapon recoil are layered separately from authoritative gameplay values.

That same separation should now expand engine-wide.

---

# 5. Proposed Xziel architecture

## 5.1 Keep gameplay authoritative

Do not rewrite working zombie rules merely to modernize graphics.

Keep authoritative:
- QuakeC gameplay;
- zombie/round state;
- weapon damage/cadence;
- collision;
- interaction logic;
- economy;
- quest state;
- game simulation;
- deterministic gameplay timers.

Expose a stable rendering/audio snapshot:

```c
typedef struct XzPresentationFrame {
    XzCamera camera;
    XzEntitySnapshot *entities;
    uint32_t entityCount;
    XzLightSnapshot *lights;
    uint32_t lightCount;
    XzFxEvent *events;
    uint32_t eventCount;
    XzAudioEvent *audioEvents;
    uint32_t audioEventCount;
    double simulationTime;
} XzPresentationFrame;
```

The exact ABI can evolve, but the boundary matters.

## 5.2 Add a Render Hardware Interface

Target:

```
                Xz RHI
             /          \
       GLES3 backend   Vulkan backend
             \          /
             shared renderer
```

Keep GL4ES/legacy GLES2 as a compatibility path during migration.

Do **not** begin by deleting the working renderer.

Preferred rollout:

1. legacy GL4ES remains fallback;
2. create RHI resource/command abstractions;
3. GLES3 backend first;
4. renderer feature parity;
5. Vulkan backend;
6. high-tier Vulkan-only features where beneficial;
7. retire GL4ES only after device coverage proves safe.

Core RHI objects:
- buffer;
- texture;
- sampler;
- shader;
- pipeline;
- render target;
- framebuffer/render pass abstraction;
- command list;
- fence/synchronization primitive;
- GPU timestamp query;
- transient resource pool.

---

# 6. New renderer design

## 6.1 Forward+ / clustered-lighting direction

A mobile forward renderer is a strong fit for Xziel's FPS use case.

Longer-term target:
- tiled or clustered light assignment;
- bounded dynamic lights;
- GPU-friendly material system;
- shadow budget;
- reflection probes;
- baked GI as primary indirect solution.

Avoid jumping immediately to a full desktop deferred renderer.

## 6.2 Linear-space PBR

Standardize materials around physically meaningful values.

Base model:
- baseColor;
- normal;
- roughness;
- metallic;
- AO;
- emissive;
- alpha mode;
- optional height/detail data.

Suggested packed texture layout:

```
BaseColor: RGB + optional alpha
NormalRoughness: XY/XYZ normal + roughness
MRAO: metallic + roughness/AO allocation depending format
Emissive: optional / shared atlas where practical
```

Exact channel allocation should be chosen after ASTC block-size tests.

Shading target:
- Lambert or energy-aware diffuse;
- GGX microfacet specular;
- Schlick Fresnel;
- Smith visibility;
- reflection probes;
- SH diffuse probes.

## 6.3 Tiered shading

Xziel should copy CODM's philosophy of tiered approximation.

Example tiers:

### Tier 0 — Compatibility
- GLES legacy/fallback;
- lightmap/unlit/simple Lambert;
- no expensive post;
- minimal particles;
- baked lighting first.

### Tier 1 — Low
- GLES3;
- simplified PBR;
- one main shadowed directional light;
- reflection probe;
- lightmap;
- aggressive LOD/mip bias.

### Tier 2 — Medium
- full base PBR;
- higher shadow quality;
- more dynamic lights;
- better particles/decals;
- higher material quality.

### Tier 3 — High
- Vulkan/GLES3 depending device;
- higher resolution shadows;
- more lights;
- improved water/fog/hair/skin;
- higher anisotropy;
- higher VFX budget.

### Tier 4 — Ultra
- Vulkan preferred;
- high-refresh capable;
- best PBR approximation;
- extra reflection/VFX quality;
- denser particles;
- more expensive temporal/upscale features where stable.

The important part is not the names. Every expensive system must expose a bounded quality knob.

---

# 7. Lighting architecture

Target a mostly-baked mobile GI model:

- one dominant realtime sun/moon/directional light where appropriate;
- baked lightmaps for static indirect lighting;
- SH probes for dynamic characters/zombies;
- reflection probes/cubemaps;
- shadowmask / baked visibility data;
- limited local realtime lights;
- emissive/VFX lights under a strict budget.

This is much more realistic for mobile than chasing unrestricted realtime GI.

Add:
- probe volumes or grids;
- automatic probe placement tools;
- offline light validation;
- material reference scenes.

---

# 8. Dynamic Resolution + Super Resolution

A CODM-class mobile engine should not tie output resolution directly to internal render resolution.

Add:

```
display resolution != render resolution
```

Quality governor can modify:
- render scale;
- target FPS;
- shadows;
- particles;
- animation update distance/rate;
- LOD bias;
- decals;
- view distance.

### SGSR

Qualcomm Snapdragon Game Super Resolution is publicly available under a permissive license.

Reference:
https://github.com/SnapdragonStudios/snapdragon-gsr

Recommended Xziel path:

1. dynamic resolution framework;
2. SGSR1/spatial path where backend compatibility is proven;
3. native-quality comparison on Adreno;
4. keep vendor-neutral fallback;
5. SGSR2/temporal only after renderer generates reliable motion vectors + depth history.

Do not build the renderer around one vendor.

---

# 9. Xziel Adaptive Performance Governor

Create an engine-owned subsystem rather than sprinkling quality changes across unrelated code.

```
XzPerformanceGovernor
  - frame pacing
  - CPU frame time EWMA
  - GPU frame time EWMA
  - thermal headroom
  - memory pressure
  - backend/device profile
  - target FPS
  - quality state machine
```

Inputs:
- CPU frame time;
- GPU timestamps;
- refresh rate;
- thermal status/headroom;
- memory pressure;
- battery/power mode if appropriate;
- device/GPU capability;
- recent stutter history.

Outputs:
- target frame interval;
- render scale;
- texture mip bias;
- LOD bias;
- shadow distance/resolution;
- particle cap;
- decal distance/count;
- animation update rate;
- dynamic-light cap;
- volumetric/fog quality;
- reflection quality.

Use hysteresis.

Never change five expensive parameters every frame.

Suggested state machine:

```
COOL_HEADROOM
STABLE
GPU_BOUND
CPU_BOUND
THERMAL_WARNING
MEMORY_PRESSURE
RECOVERY
```

Rules must be measurable and reversible.

Modern Android reference:
- Android Dynamic Performance Framework (ADPF);
- Android thermal APIs;
- Android Frame Pacing library / Swappy.

---

# 10. Frame pacing

Raw FPS is not enough.

Xziel needs:
- stable presentation cadence;
- correct swap interval selection;
- refresh-rate awareness;
- latency-conscious buffering;
- jank telemetry.

Integrate Android Frame Pacing where appropriate rather than relying only on generic SDL swap behavior.

Targets:
- 30;
- 45/48 where device display supports useful divisors;
- 60;
- 90;
- 120;
- 144 only for hardware with adequate sustained headroom.

A “120 FPS mode” that throttles after two minutes is not a successful mode.

---

# 11. Shader pipeline

## Build time
- define shader permutations centrally;
- strip impossible permutations;
- generate tier/backend variants;
- validate material compatibility offline.

## Runtime
- persistent pipeline/program cache;
- prewarm common pipelines during loading;
- prewarm map/weapon/VFX pipelines before first use;
- collect cache misses in telemetry;
- never compile a huge shader unexpectedly when the player fires a weapon for the first time.

This directly targets one of the stutter classes repeatedly addressed in modern CODM updates.

---

# 12. Texture and asset streaming

CODM's historical architecture publicly used texture streaming and atlases, and current packages are segmented into multiple downloadable asset packs.

Xziel should evolve from “APK contains everything and load it” toward:

```
core executable
core map bootstrap
shared low-res assets
map chunks
high-res texture packs
audio packs
optional cosmetics/models
patch pack
```

Runtime:
- async I/O;
- priority queue by camera/distance/gameplay importance;
- resident memory budget;
- mip residency;
- eviction;
- preload markers;
- background decompression;
- predictable failure/fallback.

Texture priority example:

1. weapon in player's hands;
2. immediate zombie threats;
3. nearby interactive objects;
4. room surfaces;
5. distant rooms;
6. non-visible optional content.

Formats:
- ASTC for modern Android devices;
- optional ETC2 fallback;
- prebuilt mip chain;
- atlas where it reduces state changes without exploding update cost.

---

# 13. Scene/world streaming

BSP can remain useful as gameplay/spatial data even while rendering changes.

Proposed split:

```
BSP / collision / portals / gameplay entities
          |
          +--> render-cell builder
                  |
                  +--> static mesh chunks
                  +--> material batches
                  +--> lightmap pages
                  +--> reflection/probe references
                  +--> visibility metadata
```

Do not require every room/map asset to be a monolithic render submission.

Add:
- visibility cells;
- frustum culling;
- portal/room culling where map topology makes it useful;
- optional occlusion;
- static batching;
- mesh LOD;
- distance-based shadow casters.

For a Zombies map, rooms and doors already provide excellent semantic streaming boundaries.

---

# 14. Animation modernization

Current Xziel planning correctly notes that classic MDL is frame-based.

For AAA presentation, forcing every new skeletal animation to be baked permanently into MDL is a long-term ceiling.

Recommended architecture:

```
authoritative entity
   state: pos, angle, movement, weapon, attack/reload/downed
             |
             v
presentation animation graph
             |
       GPU-skinned mesh
```

Gameplay remains independent.

Features:
- glTF 2.0 or another open skeletal import format in toolchain;
- offline conversion to engine-owned binary mesh/animation format;
- GPU skinning;
- compressed animation clips;
- animation state machine;
- aim offsets;
- additive recoil;
- IK only where budget permits;
- animation LOD;
- reduced update frequency at distance;
- impostor/static fallback at extreme range if needed.

Zombie-specific:
- locomotion variants;
- hit reactions;
- crawler transition;
- limb-loss presentation;
- head-loss state;
- attack variants;
- vault/window traversal;
- death poses;
- dismemberment masks.

Collision and damage zones remain authoritative and simple.

---

# 15. VFX system

Build an event-driven VFX layer.

Core requirements:
- pooled emitters;
- no gameplay-frame heap churn;
- bounded particle counts;
- emitter LOD;
- prewarm;
- atlas-based flipbooks;
- soft particles where supported;
- cheap fallback shaders;
- dynamic-light budget;
- decals with age/distance eviction.

Events:
- muzzle flash;
- shell eject;
- bullet impact by material;
- blood;
- sparks;
- electricity;
- fire;
- smoke;
- rain;
- fog;
- lightning;
- perk/mystery-box FX;
- zombie dismemberment.

The map/gameplay code sends semantic events; renderer decides quality.

---

# 16. Audio modernization

Current Android patch includes a fallback because SDL_mixer may contend for a second audio device.

That must eventually be replaced by a unified audio engine.

Target architecture:

```
single device
  |
mixer
  + master
  + music
  + weapons
  + zombies
  + dialogue
  + ambience
  + UI
  + reverb sends
```

Add:
- voice limits/priorities;
- distance attenuation;
- occlusion;
- indoor/outdoor acoustic zones;
- early reflection approximation;
- environment reverb;
- HDR-style priority/mixing behavior;
- compressed streaming music;
- sample preloading for latency-critical gunfire.

We do not need to copy Wwise internally to use the architectural lessons.

---

# 17. Memory architecture

AAA mobile is a memory-management problem as much as a graphics problem.

Every major system gets:
- hard budget;
- soft budget;
- telemetry;
- pressure response;
- owner tags.

Track separately:
- textures;
- meshes;
- animations;
- audio;
- VFX;
- map data;
- VM/gameplay data;
- transient GPU resources;
- staging/upload buffers.

Add high-water telemetry and leak detection in CI/device tests.

Avoid “load everything and trust Android.”

---

# 18. CPU architecture

Near-term:
- eliminate unnecessary per-frame allocations;
- jobify decompression/streaming/content prep;
- keep rendering submission bounded;
- update distant entities less often in presentation layer;
- cache expensive lookups.

Longer-term:
- job system;
- worker pool;
- task graph;
- separate I/O workers;
- renderer command building;
- animation jobs.

Gameplay does not need to become massively multithreaded immediately.

---

# 19. Device capability database

Do not hardcode “Samsung = high” or “Adreno = fast.”

Store capabilities:

```
GPU vendor/model
driver version
Android version
RAM bucket
Vulkan version/extensions
GLES version/extensions
texture formats
max render-target size
timestamp query support
program/pipeline cache behavior
known driver quirks
refresh-rate list
thermal API support
```

Combine:
- static profile;
- runtime benchmark;
- sustained runtime feedback.

Final quality is chosen by measured behavior, not phone marketing name.

---

# 20. Automated compatibility lab

One of the strongest lessons from TiMi's public process is broad automated device validation.

Xziel CI should eventually run:

### Correctness
- app launches;
- landscape orientation;
- first frame;
- map load;
- controls respond;
- weapon fires;
- zombie spawns;
- round advances;
- audio initializes;
- clean exit/reload.

### Rendering
- screenshot checkpoints;
- perceptual/golden-image comparison;
- black-frame detection;
- missing-texture detection;
- NaN/invalid-buffer detection;
- orientation/aspect test.

### Performance
- CPU frame percentiles;
- GPU frame percentiles;
- jank count;
- memory peak;
- loading time;
- thermal trend;
- sustained FPS after a long run.

### Device matrix
At minimum:
- low Mali;
- low Adreno;
- mid Mali;
- mid Adreno;
- high Adreno;
- high Dimensity/Mali;
- foldable/aspect-ratio device;
- tablet.

Emulators are not sufficient for thermal/GPU-driver validation.

---

# 21. Telemetry

Development builds should record a compact per-session report:

```
build
device profile
renderer backend
resolution / render scale
FPS avg / p50 / p95 / p99 frame time
CPU frame time
GPU frame time
shader cache misses
streaming stalls
memory high-water
texture residency
thermal state
quality transitions
map
round
crash/last stage
```

This turns “it feels laggy” into an actionable engine problem.

---

# 22. Production pipeline

AAA appearance will fail if artists can produce arbitrary incompatible content.

Build validation for:
- texture dimensions;
- compression;
- mipmaps;
- material channel packing;
- triangle count;
- LOD chain;
- animation clip count;
- skeleton bone budget;
- lightmap density;
- VFX emitter limits;
- audio format/rate;
- naming;
- missing references.

Provide standard reference scenes:
- neutral outdoor;
- dark interior;
- warm interior;
- high-contrast sun/shadow;
- wet/reflective material;
- skin/character reference;
- metal/roughness chart.

That mirrors the important TiMi lesson: rendering standards + content standards must be one system.

---

# 23. Networking note

Do not derive networking behavior from leaked binaries.

For Xziel multiplayer, target conventional robust FPS architecture:

- server-authoritative damage/state;
- input sequence numbers;
- client prediction for local movement;
- reconciliation;
- interpolation buffer for remote entities;
- bounded snapshot delta compression;
- interest management;
- anti-duplication/idempotent gameplay events;
- lag-compensation only where gameplay requires it;
- deterministic round/quest authority server-side.

This is an original architecture informed by standard multiplayer engineering.

---

# 24. Security / integrity

Do not spend engine time copying CODM's anti-tamper implementation.

For Xziel:
- signed builds;
- content manifest hashes;
- versioned network protocol;
- server-side validation;
- bounded packet parsing;
- no trusting client damage/currency/quest state;
- optional integrity check for competitive/public servers.

---

# 25. Migration plan

## Phase 0 — Baseline / no visual risk

- capture CPU/GPU/memory baselines;
- establish golden screenshots;
- create capability database;
- add frame-time telemetry;
- add memory accounting;
- add Android thermal/ADPF integration where supported;
- implement quality governor API with no-op scalers;
- establish long-run benchmark scene.

**Exit:** current game unchanged visually, but performance is measurable.

## Phase 1 — Frame pacing + adaptive quality

- Android frame pacing;
- dynamic target FPS;
- runtime render-scale abstraction;
- animation/update-distance scaler;
- particle budget scaler;
- view-distance/LOD scaler;
- thermal recovery/hysteresis.

**Exit:** stable sustained play matters more than peak benchmark FPS.

## Phase 2 — RHI + GLES3

- RHI skeleton;
- GLES3 backend;
- resource lifetime system;
- GPU timers;
- modern shader pipeline;
- render-target manager;
- legacy GL4ES fallback.

**Exit:** representative Nacht scene renders correctly through GLES3.

## Phase 3 — PBR core

- linear workflow;
- material compiler;
- GGX/Lambert;
- reflection probe;
- SH probe;
- lightmaps;
- directional shadows;
- tiered shaders.

**Exit:** one complete map room + player weapon + zombies use new PBR materials.

## Phase 4 — Streaming / scene cells

- async asset loader;
- texture residency/mips;
- ASTC packages;
- map render cells;
- static batching;
- preload zones;
- eviction policy.

**Exit:** map load memory bounded, room transitions hitch-free.

## Phase 5 — Animation/VFX

- skeletal presentation mesh path;
- GPU skinning;
- animation graph;
- animation LOD;
- pooled particle engine;
- decals;
- VFX prewarm.

**Exit:** zombie horde + weapons remain inside CPU/GPU budget.

## Phase 6 — Vulkan

- Vulkan RHI backend;
- persistent pipeline cache;
- command-buffer strategy;
- descriptor/resource binding plan;
- high-tier device allowlist during rollout;
- automatic fallback.

**Exit:** Vulkan beats or matches GLES3 in sustained benchmark and is crash-safe on tested profiles.

## Phase 7 — Super resolution / high refresh

- dynamic resolution controller;
- SGSR integration where appropriate;
- 90/120 Hz profiles;
- 144 Hz only where sustainable;
- latency/frame-pacing validation.

**Exit:** quality modes are based on sustained performance, not screenshots.

## Phase 8 — Audio + delivery

- unified audio backend;
- spatial zones/reverb;
- streaming music;
- asset-pack/update manifest;
- optional/high-resolution content packs.

## Phase 9 — Device farm release gate

Public release blocked if:
- orientation fails;
- black frame;
- shader compile spikes exceed threshold;
- memory leak/high-water regression;
- persistent thermal throttling;
- crash rate/test failure;
- map/weapon/zombie screenshot regression.

---

# 26. What should NOT be copied from COD Mobile

Do not import:
- CODM proprietary source;
- Activision/TiMi shaders copied from binaries;
- ripped maps;
- ripped characters;
- ripped gun models;
- proprietary sound banks;
- proprietary UI;
- proprietary animation data;
- proprietary server protocol;
- anti-cheat bypass logic.

Instead replicate:
- scalable renderer architecture;
- tiered PBR philosophy;
- dynamic quality control;
- streaming;
- shader caching/prewarm;
- content-production validation;
- device profiling;
- spatial-audio principles;
- automated compatibility testing.

That produces a technically serious engine without making Xziel dependent on somebody else's protected content.

---

# 27. Priority order for this repository

Based on the current Xziel source/build path, the highest-value work is:

1. **Performance telemetry + quality governor**
2. **Frame pacing / thermal integration**
3. **Renderer abstraction (RHI)**
4. **GLES3 native backend**
5. **PBR material/shader pipeline**
6. **Streaming + memory budgets**
7. **Skeletal presentation layer**
8. **VFX pooling/prewarm**
9. **Vulkan backend**
10. **Super resolution + high refresh**
11. **Unified spatial audio**
12. **full device-lab gating**

Trying to start at #9 or #10 while still relying on the legacy GL4ES path would produce complexity without a stable foundation.

---

# 28. Proposed source layout

```
source/xz/
  platform/
    android/
      xz_android_thermal.*
      xz_android_frame_pacing.*
      xz_android_device_caps.*

  perf/
    xz_frame_metrics.*
    xz_quality_governor.*
    xz_memory_budget.*
    xz_telemetry.*

  rhi/
    xz_rhi.*
    gles3/
    vulkan/

  render/
    xz_renderer.*
    xz_render_graph.*
    xz_material.*
    xz_lighting.*
    xz_shadow.*
    xz_probes.*
    xz_post.*
    xz_upscale.*

  world/
    xz_render_cells.*
    xz_visibility.*
    xz_streaming.*

  animation/
    xz_skeleton.*
    xz_anim_graph.*
    xz_skinning.*
    xz_anim_lod.*

  fx/
    xz_particles.*
    xz_decals.*
    xz_fx_events.*

  audio/
    xz_audio.*
    xz_audio_bus.*
    xz_acoustic_zone.*
```

Keep existing Vril files authoritative during migration. New systems consume state rather than forcing an all-at-once rewrite.

---

# 29. First engineering slice

The safest first implementation is **not PBR**.

Build this first:

```
XzFrameMetrics
XzDeviceCaps
XzPerformanceGovernor
```

Initial metrics:
- CPU frame ms;
- effective FPS;
- rolling p50/p95;
- frame spikes > 25/33/50 ms;
- render resolution;
- refresh rate;
- memory high-water;
- thermal status/headroom where available.

Initial scalers can be passive/no-op until each is tested.

Why first?

Because every later AAA-mobile system must answer:

> What does this cost, on which GPU, under what thermal state, and can the engine recover automatically?

Without that, “AAA” becomes visual feature accumulation instead of an engine.

---

# 30. Evidence confidence matrix

| Finding | Confidence |
|---|---|
| Unity foundation | High |
| TiMi deeply modified/extended engine/rendering | High |
| PBR / GGX / Lambert / IBL / SH / lightmaps | High |
| Four-level PBR approximation strategy | High |
| Texture streaming / atlases / shader LOD | High |
| Houdini + terrain pipeline / GPU bake | High |
| Runtime thermal/CPU/GPU adaptive scaling | High |
| Wwise spatial audio | High |
| Vulkan support on selected devices | High |
| Shader cache/prewarm optimization | High |
| High-refresh 90/120/144-class device profiles | High, release/device dependent |
| Super-resolution in modern CODM variants | High for documented regional builds |
| Current global 2026 exact Unity version | Unverified |
| Exact server tick for every current mode | Unverified |
| Exact proprietary netcode algorithms | Unverified |
| Exact current internal render graph | Unverified |
| Public availability of complete legal CODM engine source | No verified evidence |

---

# 31. Public reference set

Primary/near-primary technical references:

1. Samsung Developer — Adaptive Performance in Call of Duty Mobile  
   https://developer.samsung.com/galaxy-gamedev/gamedev-blog/cod.html

2. Samsung Developer event archive — Bringing Call of Duty to Mobile / mobile graphics material  
   https://developer.samsung.com/galaxy-gamedev/event-archive.html

3. TiMi J3 Unite Shanghai 2019 transcript  
   https://www.gamersky.com/handbooksy/201907/1199672.shtml

4. GameRes transcript of Guo Zhi / TiMi J3  
   https://www.gameres.com/844463.html

5. Audiokinetic / TiMi — Call of Duty Mobile Spatial Audio Integration  
   https://www.youtube.com/watch?v=QsIwq2DoFx4

6. Snapdragon Game Super Resolution — open implementation  
   https://github.com/SnapdragonStudios/snapdragon-gsr

7. Android Dynamic Performance Framework / performance docs  
   https://developer.android.com/games/optimize/adpf

8. Android Frame Pacing / Swappy  
   https://developer.android.com/games/sdk/frame-pacing

Reverse-engineering evidence used only for runtime-family/obfuscation observations:
- https://github.com/rodroidmods/il2cpp-dumper-rs
- https://github.com/djkaty/Il2CppInspector
- https://github.com/tien0246/Il2CppDumper-for-COD

---

## Final engineering principle

The reason COD Mobile behaves like an AAA mobile title is not one secret renderer function.

It is the combination of:

```
consistent material standards
+ scalable rendering
+ aggressive content tooling
+ streaming
+ quality tiers
+ runtime thermal control
+ device-specific optimization
+ shader/VFX prewarming
+ memory discipline
+ spatial audio
+ automated device validation
+ years of profiling
```

That combination is reproducible in an original engine.

For Xziel, the correct path is to **preserve Vril/NZ:P as the authoritative game core and progressively replace the presentation platform around it**. That gives us a realistic route from the current GLES2/GL4ES Android port to a modern mobile engine without destabilizing the zombie gameplay already working.
