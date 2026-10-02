# HAYUYA MOBILE PORTABILITY RESEARCH — ENGINE + HARDWARE REFERENCE

Research date: 2026-09-23

## Why this exists

## Coverage statement

This is a **living practical census**, not a dishonest claim that every hobby, abandoned, private or unreleased engine on Earth has public technical data. HAYUYA tracks every major/current 3D-mobile family that materially changes the asset contract, plus large-company proprietary engines when credible public evidence exists. Unknown private limits are recorded as unknown rather than reverse-engineered by guesswork.


This file defines what **portable for mobile** means to HAYUYA.

It is deliberately broader than "poly count." A mobile game can be limited by CPU/render-thread submission, GPU vertex work, pixel/fill work, material instructions, overdraw, render-target bandwidth, texture bandwidth, RAM, streaming, skinning/animation, dynamic lights and shadows, power draw, and thermal throttling. A model that looks cheap by triangle count can still be expensive if it has many material sections, huge uncompressed textures, alpha layers, expensive shaders, too many bones, or bad LOD/culling behavior.

HAYUYA therefore keeps the **source-faithful Hero Master** and derives runtime packages for device tiers. Mobile optimization must never destructively define the quality ceiling.

The machine-readable companion is:

- `tools/hayuya3d/mobile_portability.json`
- `tools/hayuya3d/mobile_portability.py`

The numeric asset ranges in that JSON are **HAYUYA house budgets**, synthesized from the public constraints below. They are not falsely presented as universal hard engine limits. Real-device profiling always overrides them.

---

## 1. The real mobile ceiling: sustained performance, not peak performance

### Android / SoC reality

Google's Android Dynamic Performance Framework documentation states that mobile SoCs have dynamic CPU clocks, different core types, power-management behavior and thermal limits. Devices can sustain high performance only for a limited period before thermal throttling. Google explicitly recommends adapting individual quality levers such as resolution, shadows, particles, effects and view distance using thermal feedback rather than waiting for severe throttling.

For HAYUYA this means:

- never validate "portable" from a short benchmark only;
- run sustained thermal tests (minimum house rule: 15 minutes; longer for final acceptance);
- preserve independent quality levers;
- prefer reducing resolution/shadow distance/effects before destroying source texture/detail unnecessarily;
- provide LODs and lower-cost materials so the runtime can adapt.

Sources:
- https://developer.android.com/games/optimize/adpf
- https://developer.android.com/games/optimize/adpf/thermal
- https://developer.android.com/games/optimize/adpf/best-practices-adpf
- https://developer.android.com/games/optimize/overview
- https://developer.android.com/games/optimize/power

### Apple / tile-based GPU reality

Apple documents its GPUs as tile-based deferred renderers. Tile memory avoids expensive traffic between GPU and system memory. Traditional multi-pass render designs that repeatedly spill G-buffer/render-target data to system memory can waste bandwidth and power.

For HAYUYA assets:

- minimize material passes and unnecessary transparency;
- do not assume desktop-style multi-pass material cost is harmless;
- make mobile material variants possible without changing the mesh identity;
- avoid generating assets that require multiple full-resolution intermediate surfaces merely to look correct.

Sources:
- https://developer.apple.com/documentation/Metal/rendering-a-scene-with-deferred-lighting-in-swift
- https://developer.apple.com/documentation/xcode/reducing-your-app-s-memory-use
- https://developer.apple.com/documentation/xcode/making-changes-to-reduce-memory-use

### Mali / tile rendering

Arm documents Mali's tile-based architecture and notes that external memory bandwidth is expensive in both performance and power. Older and current Arm guidance consistently emphasizes minimizing unnecessary external memory traffic and profiling frame construction.

For HAYUYA:

- favor opaque/PBR materials over layered transparent stacks;
- preserve texture compression and mipmaps;
- atlas/shared-material strategies matter because draw submission and bandwidth matter together;
- high vertex counts are not automatically worse than a bandwidth-heavy texture/material solution.

Sources:
- https://developer.arm.com/community/arm-community-blogs/b/mobile-graphics-and-gaming-blog/posts/the-mali-gpu-an-abstract-machine-part-2---tile-based-rendering
- https://developer.arm.com/Additional%20Resources/Video%20Tutorials/Arm%20Mali%20GPU%20Training%20-%20EP2-5

---

## 2. Portable asset interchange baseline

### glTF / GLB

Khronos defines glTF 2.0 as compact, runtime-neutral and interoperable across native and web engines. It supports meshes, material data, transforms, skins and animation.

HAYUYA's portable baseline remains GLB/glTF 2.0 unless an engine-specific export is requested.

### KTX2 / Basis Universal

Khronos KTX2 + Basis Universal provides a portable compressed-texture route that can transcode to device-native GPU formats while remaining compressed on the GPU. This reduces transfer size, GPU memory and bandwidth versus ordinary PNG/JPEG/WebP runtime textures when the target runtime supports the extension.

HAYUYA should preserve ordinary source textures for authoring/audit, but the portable package should be able to build KTX2/BasisU derivatives.

Sources:
- https://www.khronos.org/gltf/
- https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html
- https://www.khronos.org/ktx/
- https://www.khronos.org/blog/gltf-sample-viewer-1.1-released

---

## 3. Android texture portability

Google's current game guidance says ASTC is generally the best primary modern texture-compression option on Android, with ETC2 as fallback for wider compatibility. Google Play can deliver device-targeted compression variants.

Important: an 8K source texture does **not** imply an 8K runtime texture. HAYUYA may preserve 8K PBR in the Hero Master and derive 4K/2K/1K runtime variants with mips and ASTC/ETC2.

Sources:
- https://developer.android.com/games/optimize/textures
- https://developer.android.com/guide/playcore/asset-delivery/texture-compression

---

## Cross-vendor Android GPU rule

Android's own current optimization guidance is explicit that there is no universal CPU/GPU fix: profile the actual bottleneck. It recommends frame debuggers/profilers, removing unused render passes/attachments, ASTC compression, lower shader precision when sufficient, back-face culling, LOD, mesh simplification and frustum/occlusion culling. Android also warns that bottlenecks can vary substantially across GPU vendors and generations.

For custom/native engines, Vulkan is Android's primary low-level graphics API. Android notes that draw-heavy OpenGL ES games can become CPU-bound in the graphics driver and may reduce CPU/power overhead by moving to Vulkan.

PowerVR's public architecture documentation reinforces the same mobile rule as Apple and Mali: tile-based deferred rendering keeps work on-chip and reduces expensive system-memory bandwidth. Its guidance also warns that discard/alpha-test behavior can interfere with early visibility/depth optimizations.

HAYUYA therefore must never stamp an asset "portable" from a single Adreno, Mali, Apple or PowerVR test. The portable package needs explicit LOD/material/texture alternatives and cross-vendor validation.

Sources:
- https://developer.android.com/games/optimize/optimization-tips
- https://developer.android.com/games/optimize/power
- https://developer.android.com/games/develop/vulkan/native-engine-support
- https://developer.android.com/android-performance-analyzer/analyze/frame-times
- https://docs.imgtec.com/starter-guides/powervr-architecture/html/topics/tile-based-deferred-rendering-index.html
- https://docs.imgtec.com/starter-guides/powervr-architecture/html/topics/rules/do-use-on-chip-memory-efficiently-for-deferred-rendering.html

# ENGINE RESEARCH

## 4. Unreal Engine 5.8 Mobile

### Current mobile paths

UE 5.8 exposes Mobile Forward, Mobile Deferred and higher-cost desktop-renderer paths for selected high-end mobile devices.

Current feature documentation is important because many desktop UE assumptions are wrong for the standard mobile renderer:

- LOD: supported
- HLOD: supported
- texture streaming: supported
- virtual textures: supported
- occlusion culling: supported
- dynamic lighting: supported
- baked lighting: supported
- standard mobile Nanite: not supported
- TSR: not supported
- standard mobile hardware ray tracing: not supported
- Path Tracer: not supported
- Virtual Shadow Maps: not supported
- standard mobile Lumen GI/reflections: not supported

UE 5.8 also documents strict Mali Vulkan deferred G-buffer constraints in its default consistency mode: 128-bit/16 bytes per pixel, up to 4 input attachments, and up to 3 color + 1 depth fetch in the lighting pass.

### Public scene guidance

Epic's mobile performance guidance currently gives these **scene-level** recommendations:

- <= 700 draw calls for a single view
- <= 500k triangles for a single view
- a draw-call target around 700 on a Galaxy Tab S6 and <500 on lower-end hardware in its optimization guidance

These are not per-model limits.

### Asset implications for HAYUYA

- material IDs directly affect draw calls;
- HAYUYA should try to make common mobile derivatives 1-4 material sections where reasonable;
- generate LODs and HLOD/impostor-compatible geometry;
- generate simple collision;
- keep transparent layers controlled;
- build material variants that do not require unsupported desktop features;
- do not expect Nanite to rescue a bad mobile asset.

Sources:
- https://dev.epicgames.com/documentation/unreal-engine/rendering-features-reference
- https://dev.epicgames.com/documentation/unreal-engine/mobile-rendering-and-shading-modes-for-unreal-engine
- https://dev.epicgames.com/documentation/unreal-engine/performance-guidelines-for-mobile-devices-in-unreal-engine
- https://dev.epicgames.com/documentation/unreal-engine/optimization-and-development-best-practices-for-mobile-projects-in-unreal-engine

---

## 5. Unity 6 / URP

Unity's current URP is the practical mobile 3D path. Current Unity documentation exposes Forward, Forward+ and Deferred. Current docs describe Deferred as having a higher mobile performance impact than Forward/Forward+ because of additional G-buffer passes.

Unity 6 adds/expands tools that change how asset density should be thought about:

- GPU Resident Drawer reduces CPU draw submission through GPU instancing;
- GPU occlusion culling can reject occluded objects on the GPU;
- Render Graph can merge native render passes and keep resources in tile memory;
- URP quality/assets can be switched for different hardware targets;
- Adaptive Performance can expose thermal/performance conditions.

The lesson is not "Unity supports N triangles." It is that an asset must be compatible with batching/instancing, use sane material counts, have LODs, compressed textures and scalable quality.

Sources:
- https://docs.unity.com/en-us/engine/6000.7/manual/render-pipelines/universal-render-pipeline/introduction/urp-concepts/rendering-paths/comparison
- https://docs.unity.com/en-us/engine/6000.7/manual/render-pipelines/universal-render-pipeline/customizing-urp/render-graph/introduction
- https://docs.unity3d.com/jp/current/Manual/optimizing-draw-calls-choose-method.html
- https://unity.com/resources/mobile-game-optimization-in-unity-6
- https://developer.android.com/games/engines/unity/start-in-unity

---

## 6. Godot 4.x

Godot's documentation distinguishes its modern Mobile renderer from Forward+ and the Compatibility renderer.

Godot explicitly recommends:

- MultiMesh/manual instancing when drawing many identical objects;
- LOD/visibility ranges;
- occlusion culling;
- baked lighting for mobile because real-time lighting, shadows and GI can be too expensive on low-power devices;
- minimizing transparent content because transparency creates sorting/overdraw cost.

For a zombie game this directly means repeated zombies, debris, grass and props must be designed to instance/batch well.

Sources:
- https://docs.godotengine.org/en/latest/tutorials/performance/optimizing_3d_performance.html
- https://docs.godotengine.org/en/latest/tutorials/rendering/renderers.html

---

## 7. Cocos Creator 3.8

Cocos supports mesh LOD and instancing-oriented batching. Its docs also expose important batching restrictions:

- transparent models in the same batch may not sort correctly;
- non-uniform scale can produce inaccurate normals in the instancing path;
- batching support differs for plain meshes vs animation types.

Cocos documentation recommends ASTC for mobile and gives 6x6 as a practical high-quality model-texture preset.

HAYUYA implication:

- neutral transforms and good normals/tangents;
- LOD chain;
- avoid transparency-heavy assets;
- provide compressed mobile texture variants.

Sources:
- https://docs.cocos.com/creator/3.8/manual/en/engine/renderable/model-component.html
- https://docs.cocos.com/creator/3.8/manual/en/asset/compress-texture.html

---

## 8. Defold

Defold is a lightweight mobile-first engine with 3D model support through glTF/GLB and configurable render scripting.

Relevant portability constraints:

- draw calls are expensive;
- texture sampler counts are hardware-dependent;
- GPU skinning is used where supported, but fallback behavior can alter batching/instancing cost;
- Basis Universal/ASTC can reduce texture memory;
- Defold parses glTF PBR information, but does not automatically provide a full built-in PBR lighting model.

HAYUYA must therefore export usable geometry/material data without assuming a specific engine's fancy PBR renderer.

Sources:
- https://defold.com/manuals/performance/
- https://defold.com/manuals/model/
- https://defold.com/manuals/texture-profiles/

---

## 9. PlayCanvas

PlayCanvas is highly relevant because it exercises web-mobile constraints:

- WebGL2 / WebGPU execution
- browser memory limits
- draw-call overhead
- PBR, skinning and morphs
- Basis texture compression
- device-pixel-ratio fill-rate pressure

Its optimization guidance gives a rough low-end mobile target of about 100-200 draw calls.

That number is valuable as a reminder that web-mobile can be substantially tighter than a high-end native Unreal target.

Sources:
- https://developer.playcanvas.com/user-manual/optimization/guidelines/
- https://developer.playcanvas.com/user-manual/graphics/advanced-rendering/instancing/

---

## 10. O3DE / Atom

Open 3D Engine's Atom renderer is modular. Its docs explicitly say the **Low-end Rendering Pipeline** is the default for iOS/Android, while the main pipeline targets desktop-class systems.

HAYUYA implication: do not author a mobile asset that only works because a desktop renderer happens to support an expensive material feature.

Source:
- https://docs.o3de.org/docs/atom-guide/dev-guide/render-pipelines/

---

## 11. Roblox

Roblox is a major cross-device production engine/platform. Its current documentation emphasizes:

- draw calls have significant overhead;
- identical meshes with the same texture characteristics can be instanced into fewer draw calls;
- quality levels are device/platform dependent.

HAYUYA implication: repeated assets should share geometry/material/texture contracts and should not create unnecessary unique materials.

Source:
- https://create.roblox.com/docs/performance-optimization/improve

---

## 12. Flax Engine

Flax supports Android/iOS and exposes runtime resolution scaling, texture groups, per-platform mip caps and ASTC 4x4/6x6/8x8 support.

HAYUYA implication:

- portable assets should ship with mip chains;
- authoring texture size and runtime texture size are separate;
- runtime can lower mips/resolution without changing the Hero Master.

Sources:
- https://docs.flaxengine.com/manual/platforms/android.html
- https://docs.flaxengine.com/manual/graphics/overview/index.html
- https://docs.flaxengine.com/manual/graphics/textures/texture-groups.html
- https://docs.flaxengine.com/manual/release-notes/1_8/index.html

---

## 13. Stride

Stride supports Android/iOS build targets, but its public mobile optimization guidance is less prescriptive/current than Unreal, Unity, Godot and Google/Apple vendor documentation.

Policy: track it as a compatibility target, but do not let stale or under-specified guidance define HAYUYA's budgets.

Source:
- https://doc.stride3d.net/latest/en/contributors/engine/architecture/build-details.html

---

## 14. CRYENGINE Android — historical/secondary

CRYENGINE 5.x documentation contains Android/GLES/Vulkan work, including Android Vulkan evolution and 32-bit index-buffer support. However, the public mobile material is comparatively stale.

Policy: retain as historical compatibility knowledge only; do not use CRYENGINE's older Android guidance as a 2026 default budget authority.

Sources:
- https://www.cryengine.com/docs/static/engines/cryengine-5/categories/47316993/pages/44962798
- https://www.cryengine.com/docs/static/engines/cryengine-5/categories/23756816/pages/27594203

---

## 15. NetEase NeoX / Messiah

NetEase's 2025 SEC filing says NeoX was adapted to iOS and Android and that **Messiah was specifically designed as a 3D mobile engine**. NetEase describes the stack as supporting high-quality lighting, audio, special effects, physics and animation.

A separate public GDC session from NetEase's ACE Racer team documents **high-quality realistic mobile graphics at 90 FPS**, with the trade-off managed through rendering-pipeline and scene optimization.

This is useful evidence that high-end mobile should not be defined as a low-poly art target. It is also a warning not to invent proprietary internals: NetEase does not publish a universal Messiah triangle/draw-call ceiling.

HAYUYA implication:

- high-fidelity 60/90 FPS mobile is a legitimate flagship target;
- retain fallback tiers because those results depend on tightly tuned content/device combinations;
- do not label inferred proprietary internals as fact.

Sources:
- https://www.sec.gov/Archives/edgar/data/1110646/000110465926043468/ntes-20251231x20f.htm
- https://www.gdcvault.com/play/1028909/Achieving-High-Quality-90fps-Realism

## 16. GameMaker mobile — secondary compatibility reference

GameMaker is not the main authority for a 3D zombie game's high-end ceiling, but its Android documentation is useful for texture-memory discipline.

Its official docs explain that texture groups/pages affect texture swaps, RAM/VRAM residency and loading behavior. Its Android build guidance notes that 24-bit color can cost performance and that projects using surfaces, 3D graphics or large resolutions such as 1080p should generally target devices with a dedicated GPU. It also recommends a conservative 1024x1024 texture-page size when uncertain because Android hardware is fragmented.

HAYUYA implication: keep authoring resolution separate from runtime texture pages and provide smaller/compressed derivatives.

Sources:
- https://manual.gamemaker.io/lts/en/Settings/Texture_Groups.htm
- https://gamemaker.io/en/help/articles/android-compiling-your-app

## 17. Construct 3 / WebGPU / WebGL mobile

Construct 3 now has substantial 3D-model work and WebGPU support, making it useful as a browser-mobile stress reference rather than as our main AAA renderer target.

Its documentation calls out the CPU/GPU trade in WebGPU multitexturing: fewer CPU texture changes can increase per-pixel GPU work, and Construct disables multitexturing by default on mobile in Auto mode because mobile GPUs tend to be more fill-rate constrained. Its performance docs emphasize that fill rate becomes a bottleneck when pixel writes exceed memory bandwidth.

HAYUYA implication:

- minimize unnecessary full-screen transparent/effect layers;
- avoid excessive unique texture switching;
- web-mobile derivatives need stricter material/effect budgets than native flagship builds.

Sources:
- https://www.construct.net/en/make-games/manuals/construct-3/project-primitives/projects
- https://www.construct.net/en/make-games/manuals/construct-3/tips-and-guides/performance-tips

## 18. libGDX / lower-level mobile framework

libGDX is a framework rather than a full automatic scalability engine. Its current documentation uses OpenGL ES 2.0 by default and can enable ES 3.0 on Android; WebGL 2 maps to its GL3-style path on the web.

Because a lower-level framework leaves batching, LOD, streaming, materials and quality scaling to the game developer, it reinforces HAYUYA's engine-neutral rule: portable output cannot depend on an engine automatically fixing expensive content.

Sources:
- https://libgdx.com/wiki/graphics/opengl-es-support
- https://libgdx.com/features/

## 19. Frameworks vs engines

MonoGame and similar lower-level frameworks are intentionally tracked as a separate class. They can render 3D on mobile, but they do not provide a single authoritative content ceiling. The developer owns most rendering policy.

For HAYUYA that means the portable artifact must carry enough neutral structure to survive without engine magic:

- clean mesh hierarchy
- GLB/glTF representation where supported by the target toolchain
- LOD metadata/assets
- simple collision
- PBR maps plus cheaper material variants
- texture-size/compression tiers
- explicit scale and orientation

# LARGE PRODUCTION GAME / PROPRIETARY ENGINE LESSONS

## 20. Call of Duty Mobile — TiMi / Unity / Samsung

Samsung's engineering write-up describes Call of Duty Mobile as using PBR materials and high-resolution textures with heavy CPU/GPU load.

The project exposed separate runtime controls for:

- shadow distance
- foliage LOD
- animation rate/LOD
- target frame rate

The case study describes bottleneck detection plus thermal stages instead of waiting for OS throttling. In its tested BR battles Samsung reports about 7% higher average FPS and average temperature about 2C lower, max about 3C lower, with its adaptive strategy.

**HAYUYA lesson:** assets need independent LOD, shadow, material and animation-cost levers.

Source:
- https://developer.samsung.com/galaxy-gamedev/gamedev-blog/cod.html

---

## 21. PUBG Mobile — Tencent / Unreal

Epic's public development write-up for PUBG Mobile describes real problems from a huge map, dense objects, memory pressure, render-thread load and animation/vehicles.

Publicly described optimizations include:

- async loading because the map cannot all stay in memory;
- combining light/shadow maps to reduce texture samples;
- simplifying pixel-shader features;
- Android texture streaming;
- FOV/distance culling;
- shrinking static-mesh proxy data;
- dynamic instancing;
- using the same material across LODs to reduce shader switches;
- simplifying distant shaders.

**HAYUYA lesson:** map portability requires streaming/scene assembly beyond individual model generation. Individual assets must nevertheless be streamable, instancing-friendly, material-stable across LODs and cheap at distance.

Source:
- https://www.unrealengine.com/blog/chn-pubg-mobile-ue4-development-experience?lang=zh-CN

---

## 22. Honor of Kings — Tencent

Tencent's GDC 2023 session states that the target hardware spans entry-level phones to the latest devices and discusses optimizations that helped ship at **1080p 60 FPS** while serving a very large audience.

**HAYUYA lesson:** "entry level through flagship" is a tier system, not one asset. HAYUYA needs derivatives.

Source:
- https://www.gdcvault.com/play/1029284/Practical-High-Performance-Rendering-On

---

## 23. Tencent CROS / SmartGI / NanoMesh research

Tencent publicly identifies CROS as an in-house game engine and has described mobile/cross-platform work including SmartGI and NanoMesh/adaptive LOD research.

**HAYUYA lesson:** high-end mobile fidelity increasingly depends on smart LOD, specialized lighting, runtime scalability and minimizing preprocessing/manual asset work.

Sources:
- https://www.tencent.com/en-us/articles/2201541.html
- https://www.tencent.com/tencent-games-shares-insights-and-technologies-at-gdc-2024/

---

## 24. Arena Breakout — Tencent / MoreFun

Tencent's GDC 2024 schedule includes public sessions titled:

- "144 FPS Rendering On Mobile: Arena Breakout Frame Prediction"
- "Next Level of Mobile Graphics: Ray Tracing in Arena Breakout"

This proves that flagship mobile paths can go well beyond conservative baseline rendering. It does **not** mean those features are portable to broad devices.

**HAYUYA lesson:** flagship package may retain much higher geometric/material quality, but fallback derivatives remain mandatory.

Source:
- https://www.tencent.com/en-us/articles/2201793.html

---

## 25. Lineage W — NCSoft / Unreal / Android ADPF

Google's case study is especially valuable because it demonstrates the difference between peak and sustained performance.

During a 30-minute Pixel 6 test at a forced 60 FPS target, performance without proper adaptation fell from 60 to 32 FPS as thermal headroom hit the severe-throttling threshold at roughly four minutes. Default Unreal scalability improved things but did not fully solve heat. Integrating **Lineage W's own quality settings** with ADPF produced a more stable sustained result.

**HAYUYA lesson:** a portable asset must expose quality reductions the game can choose intelligently.

Source:
- https://developer.android.com/stories/games/lineagew-adpf

---

## 26. Asphalt 9 — Gameloft

Google's Game Mode case study describes different modes:

- 60 FPS on supported hardware;
- 30 FPS on lower-end/battery modes;
- battery mode removes expensive reflection/ray-tracing work and depth of field, and simplifies motion blur/weather shaders.

**HAYUYA lesson:** runtime quality should be a matrix of features, not simply "same render at lower FPS."

Source:
- https://developer.android.com/stories/games/gameloft-gamemode

---

# HAYUYA ZOMBIE-GAME RULES

## 27. Zombie characters

A zombie game creates a worst-case combination of:

- many animated characters
- skinning/bone updates
- shadows
- transparent blood/hair/clothes
- repeated materials
- close hero zombies and far crowd zombies

HAYUYA must therefore generate:

1. **Hero Master**
   - highest source-faithful geometry
   - high-resolution PBR
   - no runtime destruction

2. **Flagship runtime LOD0**
   - selective high detail
   - 4K only where justified
   - clean material partitioning
   - scalable shadow/material path

3. **High/Balanced/Compatibility variants**
   - lower mesh density
   - 2K/1K textures
   - fewer material slots
   - reduced translucent layers
   - lower-cost shadow variant
   - animation LOD metadata-ready

4. **Crowd version**
   - aggressive mesh/texture/material simplification
   - shared atlas/material
   - shared skeleton where character design allows
   - animation update throttling supported by runtime
   - impostor/HLOD path where useful

The runtime ranges are stored in `mobile_portability.json`.

---

## 28. Props

For props, **draw/material cost is often more important than raw triangle count**.

Rules:

- preserve a dense Hero Master;
- use one material where possible, 2-3 only when visually justified;
- bake tiny material differences into atlases/masks;
- generate LODs;
- simple collision only;
- instance repeated props;
- avoid unique shader permutations for every prop.

---

## 29. Architecture / church / environment pieces

Do not treat a whole map as one Hayuya object.

For architecture HAYUYA should generate **modular, streamable pieces**:

- wall sections
- floor sections
- roof
- doors/windows
- altar
- columns/statues
- repeated trim
- props
- collision proxies
- HLOD/impostor-friendly clusters

The future map/environment generator should reuse:

- HAYUYA reference pool
- Judge
- Material Bridge
- Mesh Doctor
- portability knowledge base
- GamePrep

but add:

- world scale
- modular decomposition
- streaming cells
- occlusion planning
- navmesh/collision zones
- lightmap density
- scene draw-call/material budgets
- vegetation crowds
- spawn/navigation constraints

This is intentionally separate from object/character image-to-3D.

---

## Physical KTX2 / Basis Universal delivery

HAYUYA now has an executable physical texture-delivery stage rather than only a compression recommendation.

Pinned toolchain:

- glTF Transform CLI 4.5.0
- Khronos KTX-Software 4.4.2

The runtime GLB path:

1. resizes textures to the selected tier ceiling;
2. uses UASTC for normal, occlusion and metallic-roughness slots;
3. uses ETC1S for remaining compatible textures;
4. generates mipmaps;
5. writes KTX2 payloads into the GLB;
6. requires KHR_texture_basisu;
7. audits that every referenced runtime texture uses the extension and every embedded image is image/ktx2.

The original Hero Master is untouched, and each tier keeps its non-KTX2 GLB sibling for runtimes that do not consume KHR_texture_basisu.

Important terminology: KTX2/Basis Universal is a universal compressed delivery representation. It may be transcoded to native GPU formats such as ASTC or ETC2 at runtime or by an engine-specific build pipeline. HAYUYA must not claim that a BasisU GLB already contains native ASTC/ETC2 blocks unless a separate native-format packaging stage actually generated them.
# PORTABILITY ACCEPTANCE TEST

An asset/package cannot be called mobile-portable merely because it opens on Android/iOS.

HAYUYA should require:

- valid Hero Master retained;
- runtime LOD0-LOD3;
- lower-resolution texture derivatives;
- compressed-texture plan;
- mipmaps;
- material-slot audit;
- transparency/overdraw warning;
- collision proxy;
- GLB validation;
- scale/orientation metadata;
- rig/skin audit for characters;
- source-vs-runtime visual comparison;
- profile label: compatibility / balanced / high / flagship;
- real-device test required before final product acceptance;
- sustained thermal test, not a five-second FPS screenshot.

## The rule

**PORTABLE ≠ LOW QUALITY.**

Portable means:

> Keep the highest-quality source-faithful master, then create enough validated runtime derivatives that the same visual identity can survive from lower-end mobile through flagship mobile without forcing one device class to define the art ceiling.
