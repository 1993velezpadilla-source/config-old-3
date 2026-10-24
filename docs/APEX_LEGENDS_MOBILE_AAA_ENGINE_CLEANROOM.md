# Apex Legends Mobile → Xziel AAA-Mobile Clean-Room Engine Study

Research date: 2026-09-21
Target: Xziel / NZ:P Android engine modernization
Method: public technical talks, official EA/Respawn/LIGHTSpeed materials, public reverse-engineering evidence used only to identify runtime/format characteristics, and clean-room architectural reconstruction.

## Executive conclusion

Apex Legends Mobile is one of the most useful public AAA-mobile case studies for Xziel because its engine team disclosed unusually specific rendering architecture.

The mobile game was rebuilt as a standalone mobile title by Respawn with LightSpeed & Quantum rather than being a direct port of the PC/console Source-engine executable. Public sources identify Unreal Engine 4 as the mobile engine family, while reverse-engineering community evidence places early versions around UE 4.23 with a heavily customized asset/runtime stack. Exact later shipping fork revision should not be treated as fully verified.

The important lesson is not "switch Xziel to Unreal." It is that LightSpeed took a general engine and replaced or extended the parts that were unsuitable for mobile GPUs.

The most transferable systems are:

- UE4 Mobile Forward-derived renderer
- heavy use of baked lighting/lightmaps
- ILC/probes for dynamic objects
- very fine-grained world streaming
- LevelLOD/HLOD-style distant representation
- material consolidation using texture arrays
- HISM-based static batching
- custom LRU-assisted instance-buffer reuse
- custom uniform-based dynamic batching
- CPU triangle-cluster culling inspired by meshlets
- software-raster occlusion support
- custom mobile Lite-HDR render path
- pass amortization across frames
- fitted ACES-style tonemapping
- render-target load/store minimization for tile-based GPUs
- per-device culling/quality granularity
- sustained-power optimization, not peak FPS only

## 1. Verified development structure

EA/Respawn stated that Apex Legends Mobile was developed by a dedicated Respawn mobile team together with LightSpeed & Quantum Studios.

The title ran on separate servers and was built specifically for mobile rather than sharing cross-play with PC/console.

Official minimum target during regional testing included:
- Android 6.0+
- OpenGL ES 3.1+
- roughly 2 GB RAM minimum for selected supported Android devices
- support targets reaching hardware several years old

This is important because the renderer architecture had to scale from low-end GLES-class hardware to high-refresh flagship phones.

Public technical target from the project engine team:
- mainstream devices: roughly 40–60 FPS
- flagship devices: 90–120 FPS target territory
- explicit concern for sustained power/thermal behavior

## 2. World lighting strategy

Apex Mobile did not attempt unrestricted fully dynamic GI.

Instead it exploited the fact that the large BR environment did not require a day/night cycle.

Primary strategy:
- baked static global illumination
- extensive lightmaps
- ShadowMask integrated with baked data
- Directional SH information retained for higher-quality tiers
- single-point SH lighting for smaller objects
- multi-point SH bake for larger/complex primitives
- ILC for characters and vehicles
- optimized/adaptive ILC placement

For Xziel this translates directly to:

static rooms/walls/architecture:
    lightmap + baked visibility/shadow

zombies/players/weapons:
    probe/SH indirect light + selected realtime direct lights

This is a much better mobile tradeoff than attempting desktop-style realtime GI.

## 3. Shadow architecture

Apex Mobile used CSM for the primary dynamic shadow component, but reduced the necessary cascade distance by relying heavily on baked shadow information.

Key ideas:
- baked distance-field-like ShadowMask in lightmap alpha
- shorter CSM range
- cached static ShadowDepth
- low-quality mode where only dynamic objects cast realtime shadows
- static objects fall back to baked ShadowMask/probe shadowing

Xziel implementation lesson:

Quality 0:
- baked static shadow only
- dynamic actor blob/projected shadow optional

Quality 1:
- one short-range CSM cascade set
- baked static world shadow

Quality 2+:
- higher-resolution short-range CSM
- selected dynamic point/spot shadow budget
- cached static caster depth

Do not increase CSM distance simply because the renderer can.

## 4. Fine-grained world streaming

Apex Mobile's BR world was roughly kilometer-scale and very dense.

The engine team reported maps with 500+ sublevels.

They organized those sublevels into distance-based loading layers and used LevelLOD representations for distant content.

They also modified WorldComposition with:
- work spread across frames
- loading prediction

Benefits:
- fewer primitives resident
- fewer actors/UObjects resident
- lower memory
- lower InitViews cost
- more predictable streaming

### Xziel equivalent

A Zombies map is smaller, so we do not need hundreds of cells, but the architecture is still useful.

Build semantic cells around:
- room
- hallway
- exterior courtyard
- upper floor
- basement
- inaccessible vista
- special-event zone

Each cell owns:
- render meshes
- material refs
- lightmap pages
- probes
- VFX
- ambient audio
- decals
- optional high-res textures

Gameplay collision/entities can remain loaded independently from presentation assets when required.

Add predictive prefetch from:
- current room
- open doors
- player velocity
- known traversal graph
- stair/teleporter destination
- round/event state

## 5. Material consolidation

Apex Mobile identified multi-material buildings as a major draw-call source.

Instead of flattening all detailed textures into one giant atlas, the team used Texture Arrays for tiling materials.

Why:
- ordinary atlas tiling creates UV discontinuities
- automatic mip selection can jump at atlas boundaries
- seams/flicker become visible
- texture arrays preserve continuous local UV behavior while selecting a layer

They also extended the approach with multi-slice composition for multiple effective resolutions.

### Xziel material system

For repeated world surfaces:
- concrete
- brick
- wood
- metal
- plaster
- trim
- floor
- ceiling
- grime/detail

Prefer:
- texture arrays / material libraries
- small parameter set per material
- shared shader
- instance parameters
- optional masks/detail maps

Avoid:
- unique shader/material object per wall
- duplicated texture sets for minor tint differences

## 6. Static instancing

Apex Mobile heavily used HISM.

They found that visibility gaps inside an instance buffer could split one logical batch into multiple draw calls.

Their optimization:
- merge remaining visible instance ranges
- cache the merged buffer
- key cache by visible-cluster combination
- manage with LRU

Reported result:
- cache misses below ~5% in benchmark scenes
- ~95% reduction in repeated buffer assembly
- up to roughly 30–40 fewer draw calls in tested scenes

### Xziel equivalent

Create:
- XzStaticInstanceGroup
- visibility bitset/key
- XzInstanceBatchCache
- LRU of assembled visible ranges

Use it for:
- barricade planks
- debris families
- repeated wall modules
- lamps
- chairs/tables
- foliage
- pipes
- crates
- repeated environmental props

## 7. Custom dynamic batching

Apex Mobile evaluated UE GPUScene but found it problematic for broad mobile compatibility.

Problems described:
- compute-shader dependency
- Android vertex-stage texture-buffer fetch
- extra PrimitiveID mapping
- on some Qualcomm devices, GPU behavior could shift from tile/binning-friendly behavior toward a less favorable mode

Their solution:
- assemble compatible PrimitiveData on CPU each frame
- upload into a Uniform array
- vertex shader indexes using InstanceID
- cap batch size aggressively because uniform space is bounded

Reported benchmark:
- low-end frame time improved from about 28 ms to about 22 ms versus their tested GPUScene path

### Xziel lesson

Do not assume "GPU-driven" is automatically faster on every phone.

For broad Android support create two modes:

Mode A — compatible CPU batch
- CPU prepares compact per-instance records
- UBO/uniform storage
- gl_InstanceID
- no compute requirement

Mode B — advanced GPU-driven/Vulkan
- SSBO/device-address/indirect path
- only enabled when telemetry proves it is faster

PerformanceGovernor chooses the path by device profile.

## 8. Occlusion + screen-size culling

Apex Mobile used:
- frustum culling
- screen-percentage/screen-size culling
- partition-aware culling
- software-raster occlusion

This matters for Zombies because a player can see through doorways/windows into rooms containing many actors/props.

Xziel should implement culling layers:

1. world/room visibility
2. object frustum
3. minimum projected size
4. occlusion
5. cluster-level culling
6. per-system quality budget

## 9. CPU triangle-cluster culling

This is the most interesting Apex Mobile-specific technique.

Problem:
Large rocks, mountains and landmarks have huge bounding boxes. The object bounding box intersects the camera frustum even if most triangles are invisible.

GPU-driven/meshlet approaches were considered but broad mobile compatibility and compute cost were concerns.

Apex Mobile built a CPU cluster-culling pipeline inspired by GPU-driven rendering and meshlets.

### Offline/DDC stage

- analyze triangle spatial structure
- partition mesh into clusters
- construct a binary hierarchical cluster tree
- reorder index buffer
- each cluster corresponds to contiguous index-buffer sections
- store only small metadata

### Runtime

After ordinary object culling:
- traverse cluster hierarchy depth-first
- test cluster AABB against frustum
- test against software-raster depth/occlusion
- if parent invisible: skip children
- if parent fully inside frustum: children can inherit frustum-visible status
- emit visible index sections
- merge sufficiently small invisible gaps where beneficial

Reported:
- >30% triangle rejection in many views
- >60% triangle rejection in favorable street/interior cases
- roughly 5–10% draw-call rejection in favorable cases
- culling work generally kept under ~0.5 ms
- feature enabled broadly across devices with different granularity tiers

### Why this is ideal for Xziel

Our enhanced maps will contain:
- larger architectural meshes
- richer rubble
- pipes
- broken walls
- stairs
- roof structures
- exterior vistas

Classic BSP/PVS helps at room scale, but it does not solve overdraw/triangle waste inside a visible large model.

Proposed system:

```
XzMeshClusterTree
  node:
    aabb
    firstIndex
    indexCount
    leftChild
    rightChild
    flags
```

Build offline.

Runtime:
```
PVS/room
 -> object frustum
 -> cluster hierarchy
 -> optional software occlusion
 -> visible contiguous sections
 -> draw merging
```

This can coexist with BSP rather than replacing it.

## 10. RenderPass optimization

Apex Mobile explicitly optimized around tile-based mobile GPU behavior.

Core observation:
- render-target Load/Store is expensive
- render-pass changes increase bandwidth
- high bandwidth increases power and heat
- high FPS makes these costs worse

Their base was UE4 Mobile Forward.

This strongly supports our earlier decision that Xziel should use a forward/Forward+-style mobile renderer rather than a desktop-heavy deferred path.

## 11. HDR optimization

Standard UE4 mobile HDR path included:
- base pass
- bloom passes
- eye adaptation
- tonemapping/LUT
- final LDR output

Apex Mobile reduced this cost.

### Bloom
- amortized selected low-frequency/low-resolution bloom passes across frames
- removed two passes from the per-frame burden

The project engineer noted that at ~40–50 FPS, alternating low-frequency bloom work was difficult to perceive.

### Tonemapping
Instead of generating/sampling a LUT every frame/path:
- fit the UE filmic response using an ACES-based approximation
- precompute fit parameters
- evaluate with few runtime instructions
- preserve familiar artist controls

### Auto exposure
- small-resolution luminance statistics
- PixelShader-based path
- amortized across frames
- when bloom exists, reuse bloom's reduced-resolution output

## 12. LDR improvement

Apex Mobile did not treat low-end LDR as simply "turn everything off."

They added cheap tonemapping into the LDR base pass and used automatic pre-exposure adjustments so the appearance stayed closer to the HDR path.

The project presentation explicitly notes a similar COD Mobile technique here.

This is important confirmation that the two AAA-mobile projects converged on the same philosophy:
- keep the visual language consistent
- change the mathematical cost underneath

## 13. Lite-HDR

Apex Mobile built a custom Lite-HDR path specifically for mobile GPUs.

Design goal:
- back-buffer-only from base pass to UI where possible
- avoid render-target switching
- avoid unnecessary load/store
- use subpasses/framebuffer fetch-like behavior
- preserve key HDR benefits

Approaches mentioned:
- memoryless MRT for HDR intermediate information
- subpass fetch
- Pixel Local Storage on Mali where appropriate
- HDR32bpp-style encoding when float backbuffer is unsuitable
- ImageStore-based luminance statistics

Benefits observed:
- reduced bandwidth
- reduced last-level-cache traffic
- GPU time improvement in tested iOS cases

Limitations in the documented implementation:
- requires framebuffer fetch or analogous capability
- bloom/AA support was not complete at the time of the talk

### Xziel renderer implication

Our RHI should expose capabilities, not assume one HDR path.

```
XZ_COLOR_PATH_LDR
XZ_COLOR_PATH_HDR
XZ_COLOR_PATH_LITE_HDR
```

Capability flags:
- framebuffer fetch
- input attachment/subpass
- memoryless attachment
- pixel local storage
- float color target
- HDR packed format
- image load/store

Then device profile selects the cheapest path preserving desired appearance.

## 14. Mobile forward renderer

Apex Mobile publicly states that the project was based on UE4 Mobile Forward.

This reinforces the Xziel plan:

- forward/Forward+ base
- static baked GI
- limited realtime shadow/light budget
- clustered/tiled lights only when useful
- one dominant directional source
- cheap transparent/VFX integration
- low bandwidth

Do not imitate a desktop G-buffer architecture simply because it looks more modern on paper.

## 15. High refresh + thermal philosophy

The Apex team explicitly targeted 40–60 FPS on mainstream devices and 90–120 on newer flagships.

They also emphasized that simply reaching 60 FPS was not enough because thermal/power behavior determines whether the framerate survives.

For Xziel:

Every performance mode needs:
- cold benchmark
- 5-minute test
- 15-minute test
- 30-minute sustained test
- thermal state history
- FPS/frame-time percentiles
- power proxy where accessible

A 120 Hz profile that collapses after thermal saturation is not a valid shipping profile.

## 16. Asset/runtime evidence

Public community tooling identifies the game as UE4-family and early builds as compatible with UE 4.23-oriented extraction tooling.

Community reverse-engineering also reported:
- skeletal meshes
- animations
- textures
- custom encryption in later packages
- ACL-style animation compression appearing in later builds

This evidence is useful only to understand technology choices.

Xziel should not import proprietary Apex assets or encryption logic.

The transferable lesson is:
- compressed skeletal animation is expected at AAA mobile scale
- engine-owned cooked packages need versioning
- runtime assets should be streamed/decompressed on demand

## 17. Animation lesson for Xziel

Apex's gameplay depends on:
- sprint
- slide
- climb
- jump
- landing
- weapon swaps
- reloads
- abilities
- third-person readability

The mobile package evidence supports a real skeletal-animation pipeline rather than frame-baked meshes as the long-term solution.

Our migration should therefore preserve classic MDL only as compatibility content.

New high-quality assets:
- skeleton
- compressed clips
- per-bone tracks
- additive aim/recoil
- event markers
- animation LOD
- GPU skinning

Gameplay physics remain independent.

## 18. Networking caution

Apex Mobile ran on separate mobile servers.

Official regional testing specifically targeted:
- matchmaking
- progression
- backend infrastructure
- live operations

Official later notes mention:
- device/server performance optimization
- latency focus
- matchmaking adjustment

However, public evidence is not sufficient to claim the exact proprietary mobile snapshot/tick/prediction implementation.

Xziel should use a standard server-authoritative FPS design rather than invent details and calling them Apex's netcode.

## 19. CODM + Apex Mobile combined architecture

CODM gives Xziel:
- device/thermal adaptive performance
- quality governors
- scalable PBR
- content pipeline
- texture streaming
- shader LOD/cache/prewarm
- broad device adaptation
- spatial audio lessons

Apex Mobile adds:
- very fine-grained world streaming
- material consolidation via arrays
- HISM-like instancing
- LRU instance-range cache
- mobile-friendly CPU dynamic batching
- software occlusion
- hierarchical CPU triangle-cluster culling
- render-pass bandwidth discipline
- frame-amortized bloom/exposure
- ACES-fit tonemapping
- Lite-HDR/subpass pipeline

Combined target:

```
                     XZIEL
                       |
        +--------------+--------------+
        |                             |
 authoritative game             presentation engine
 Vril/QuakeC                    Xz modern runtime
        |                             |
        |                    +--------+--------+
        |                    |                 |
   zombie/gameplay         world             renderer
                            streaming          RHI
                              |                 |
                          render cells     GLES3/Vulkan
                              |                 |
                         cluster tree      LDR/LiteHDR/HDR
                              |                 |
                         culling/batch     PBR/lighting/VFX
```

## 20. Proposed new modules

```
source/xz/world/
  xz_world_cell.*
  xz_stream_predictor.*
  xz_level_lod.*
  xz_mesh_cluster_builder.*
  xz_cluster_culling.*
  xz_occlusion_raster.*

source/xz/render/
  xz_instance_group.*
  xz_instance_cache.*
  xz_dynamic_batch.*
  xz_color_pipeline.*
  xz_tonemap.*
  xz_exposure.*
  xz_bloom_scheduler.*

source/xz/rhi/
  xz_renderpass_caps.*
  xz_framebuffer_fetch.*
  xz_memoryless_targets.*
```

## 21. Implementation order from Apex findings

### Slice A — World cells
Add presentation-level cells around current map/BSP.
No gameplay behavior changes.

### Slice B — Static instance grouping
Batch repeated props/material-compatible surfaces.

### Slice C — Texture arrays
Create array-backed tiling material family.

### Slice D — Mesh cluster cooker
Offline cluster generation + reordered index buffers.

### Slice E — CPU cluster culling
Frustum only first.
Then software occlusion.

### Slice F — Mobile RenderPass abstraction
Model attachment lifetime/load/store explicitly.

### Slice G — cheap LDR
Tonemap/pre-exposure inside cheapest path.

### Slice H — optimized HDR
Bloom/exposure amortization.

### Slice I — LiteHDR
Only on devices exposing the required fetch/subpass behavior.

## 22. Release metrics

For every renderer feature capture:

- CPU frame ms
- GPU frame ms
- draw calls
- triangles submitted
- triangles rejected
- batches
- batch cache hit rate
- render target load/store bytes where profiler supports it
- texture residency
- memory peak
- thermal state
- 1%/0.1% frame-time tails
- visual screenshot comparison

Do not accept optimization based solely on average FPS.

## 23. Specific performance gates

### Cluster culling
Target:
- <0.5 ms CPU on representative mid-tier
- measurable triangle reduction
- no net CPU regression

### Instance cache
Target:
- >90% stable cache hit in repeated room views
- no unbounded memory growth

### Streaming
Target:
- no visible hitch at door/stair traversal
- predictable memory high-water

### LiteHDR
Target:
- image within defined perceptual tolerance of HDR
- bandwidth/GPU win on supported tile GPUs
- automatic fallback when unsupported

## 24. Key architectural lesson

Apex Legends Mobile did not become AAA by blindly enabling expensive Unreal features.

The engine team repeatedly replaced generic/desktop-oriented mechanisms with mobile-specific ones:

- GPUScene -> uniform dynamic batching where faster
- large object bounds -> cluster-level CPU culling
- full HDR chain -> optimized HDR / LiteHDR
- giant always-resident world -> hundreds of fine-grained streamed sublevels
- generic material layout -> array-based reuse
- long realtime shadow range -> baked shadow + short CSM
- every-frame post work -> selected cross-frame amortization

That is exactly the mindset Xziel needs.

## 25. Recommendation for Xziel

The best technical synthesis is not "copy CODM" or "copy Apex Mobile."

Use:

**CODM philosophy**
- scalable quality
- device tiers
- thermal governor
- PBR consistency
- streaming/prewarm

plus

**Apex Mobile rendering**
- fine world cells
- CPU-friendly batching
- cluster culling
- bandwidth-first RenderPass design
- LiteHDR
- cheap fitted tonemapping

while retaining:

**Vril/NZ:P strengths**
- mature zombie gameplay
- compact native code
- BSP spatial structure
- low baseline CPU/memory
- deterministic classic gameplay systems

That combination can produce an engine far more efficient than trying to transplant a general-purpose AAA engine wholesale.

## Public references

Primary/near-primary:
- EA / Respawn limited regional launch:
  https://www.ea.com/ea-studios/ea-sports/news/apex-legends-mobile-lrl
- EA mobile requirements / FAQ:
  https://www.ea.com/ea-play/news/apex-legends-mobile-faq
- LIGHTSPEED Studios game/developer information:
  https://www.lightspeed-studios.com/m/gamedetail/apex-mobile.html
- TGDC 2022 rendering optimization transcript:
  https://www.gameres.com/896788.html
- Unreal Circle recording reference for Chen Yugang's rendering talk:
  https://www.d-arts.cn/article/article_info/key/MTIwMjYzNzQ0NzmDz4llr6ywcw.html

Community runtime evidence:
- Gildor UE Viewer forum technical support thread:
  https://www.gildor.org/smf/index.php?topic=7731.0

Community runtime evidence is not used as a source of proprietary code/assets.
