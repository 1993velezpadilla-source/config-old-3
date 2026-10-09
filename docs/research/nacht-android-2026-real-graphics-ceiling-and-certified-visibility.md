# Nacht Android: visual ceiling, real 2026 shipped references, and provably invisible geometry

Research branch only. Date: October 9, 2026. The archived source stage is a **Pavlov UE4.21 Nacht reconstruction**, **NOT an original official BO3 T7 source**. Nothing below demonstrates shipping Android FPS for this Godot build.

## The user's strict quality rule

1. The player can rotate 360° while crouching/standing/jumping, look through ALL reachable windows, upstairs openings and outdoor passages, and move through all future unlocked areas. No deletion is permitted merely because an actor is 55/90/150 m from the central building.
2. Near/interactable source geometry/textures/collisions and anything seen through windows stay at original quality, except honest measured LOD if pixel equivalent.
3. If a model is visible at long range, retain its silhouette. Replace only with independently verifiable cheaper native source-derived geometry, actor-local mip/texture variant or impostor that preserves source form. Distant alpha foliage silhouette and tree outlines matter.
4. Permanently exclude an actor from rendering ONLY after a **complete audited camera-reachability proof** spanning all playable nav polygons, eye heights, door/board states, windows and outdoor areas, plus conservative occlusion with opaque *fixed* geometry. Sparse screenshots/camera rays cannot certify 100% invisible.
5. Shared DDS must never be globally downsampled for background. The original source 440-far-actor data proves 12/14 authored materials shared with other actors and only ~0.79 MiB of original DDS is unique to these far actors. Use per-actor source-image derivatives. The 340 authored vista-tagged actors are **candidates, NOT certified unseen**.
6. Use render frustum culling, portal/room visibility and Godot Mesh LOD/HLOD/occlusion when appropriate, but distinguish temporary runtime non-rendering from irreversible asset deletion. Keep original source project and immutable game-collision/nav identities.

### Fail-closed removal requirements

- Reachability: full actual shipping collision and navigation bake for *every* floor, exterior, opened-door state, crouch/jump point and legitimate spawn; show vertices/polygons and door-state completeness.
- Vision: all relevant camera positions and angles (360°), standing/crouching/ADS FOV, windows, all gameplay times/light states; conservative line-of-sight. Occluders must be fixed and opaque in all gameplay states.
- Occluder guarantee: neither movable doors/boards, foliage, alpha materials, zombies, nighttime darkness/fog nor current lack of draw can count as permanent occlusion.
- For any actor whose evidence is incomplete or can be visible at least once, classify **KEEP** (full-resolution near, reduced-quality source silhouette far).
- Release gate must report **ZERO certified deletions** until completeness evidence is present, not a guessed number of invisible far objects.

## What 2026 Android really demonstrates (official primary-party evidence)

These demonstrate the broader Android platform capabilities **independent of Godot** and are not performance claims for this game.

| Real released Android title / experiment | Primary-party verified Android evidence | Implication |
| --- | --- | --- |
| **Wuthering Waves 3.6**, Kuro Games | Android recommended Snapdragon 8+ Gen 1 / 8 Gen 2 / 8 Gen 3-class, ≥6 GB RAM; current installation requirement can be 65 GB. https://wutheringwaves.kurogames.com/es/main/news/detail/5272 | Large mobile 3D action worlds and rich assets are real. Installation size is **not** live texture VRAM, and the recommendation does **not** establish max graphics FPS. |
| **Where Winds Meet Android**, NetEase/Everstone | Open-world wuxia with cross-play and cross-progression to PC/console, available on Android since December 12 2025. https://www.neteasegames.com/news/WhereWindsMeet/20260226/43512_1276266.html | Real mobile immersive large 3D world, but doesn't guarantee identical graphics settings to PC/console. |
| **Delta Force Mobile**, TiMi/Garena | Full globally released tactical FPS on Android/iOS since April 2025. https://deltaforce.garena.com/es/news/anuncios/M3URNX | Closest genre benchmark for detailed first-person shooter scenes and mobile touch interface, distinct from backend Godot performance. |
| **Infinity Nikki**, Infold | Official recommended Android Snapdragon 8 Gen 2, Dimensity 9200, Google Tensor G4/Exynos 2200+, ≥8 GB RAM; minimum Snapdragon 888/Tensor G3 class ≥6 GB. https://infinitynikki.infoldgames.com/en/news/16 | High-fidelity 3D mobile with high memory/device tiers exists. |
| **Warframe Android**, Digital Extremes | Public global Android launch Feb 18 2026. Official compatibility ARM64, Android 12+, ≥4GB RAM. https://www.warframe.com/en/news/warframe-on-android-available-now | Real-time complex third-person action engine shipping on native Android; 4 GB is a stated compatibility minimum, not proof of max settings. |
| **Alien: Isolation Android**, Feral/Google Play | Full mobile port with published 11 GB game data; suggests 22 GB free space to install. https://play.google.com/store/apps/details?id=com.feralinteractive.alienisolation_android | Genuine high-fidelity atmospheric 3D AAA-like horror on Android, strongly relevant to night-time first-person Nacht. |
| **GRID Legends: Deluxe Edition Android**, Feral | Complete Android motorsport port, production 3D environments and lighting. https://feralinteractive.com/es/games/gridlegends/android-ios/ | Fast real-time 3D console-origin visuals in a mobile commercial product. |
| **Qualcomm ProjectOne UE5.4.4 on Snapdragon 8 Elite Gen 5**, official engineering demonstration, **NOT a playable shipping game** | Qualcomm says AAA high-fidelity UE5 content runs **30 FPS** in a real-time cinematic, using dedicated mobile optimizations. https://www.qualcomm.com/developer/blog/2026/01/run-unreal-engine-5-content-30fps-snapdragon-mobile | Very high ceiling on select flagship Android SOCs, but *no general guaranteed 60 FPS, no Godot parity, and no thermal-duration guarantee.* |
| **UE5 experimental mobile Lumen**, Epic Games | Lumen experimental high-end Android with Vulkan Shader Model 5 using Desktop Renderer, not automatically a low-cost Godot Mobile feature. https://dev.epicgames.com/documentation/unreal-engine/using-lumen-global-illumination-on-mobile-in-unreal-engine | Android capability != availability within current rendering path. |
| **Godot 4.6 Mobile renderer** | Vulkan RenderingDevice Mobile supports LightmapGI, glow, fog, GPU particles, decals etc., with mobile feature limits. Our actual captured research screenshots so far run Mesa `gl_compatibility`, *not physical-device Vulkan.* https://docs.godotengine.org/en/4.6/tutorials/rendering/renderers.html | Can push visually beyond current screenshot with precomputed bounce lighting, small selected dynamic local lights, good assets and careful frame budgeting. |

## Real research optimization before reducing source quality

Godot docs say automatically imported **3D scene mesh LOD** can use meshoptimizer, and **visibility ranges** permit detailed/cheap model swapping per actor without deleting the source asset:
- https://docs.godotengine.org/en/stable/tutorials/3d/mesh_lod.html
- https://docs.godotengine.org/en/stable/tutorials/3d/visibility_ranges.html
- https://docs.godotengine.org/en/stable/tutorials/3d/occlusion_culling.html

A distant vista tree's original geometry and high-res DDS can be replaced by **separate source-derived** lower-res assets for that far instance while leaving nearby copies full quality. The aggressive tier must be proven on real Godot physical Android Vulkan Mobile path, not only a desktop Mesa OpenGL screenshots workflow.

### Avoid false numbers

The research currently has 10,793 source actor transforms, 493 mesh types, 11,788,583 placed indexed source triangles and 16,595 original surface material bindings. The source texture inventory contains 718 in-use DDS ≈618 MiB compressed and hypothetical all-decoded RGBA8 mip footprint ≈2.78 GiB. These are **raw source inventories**; measured gameplay VRAM, compression formats on-device, GPU draw calls, frame time and heat are still unknown. The 415 far visual actors with property changes in research do not prove their triangles fell; Godot's `ArrayMesh.surface_get_lods()` is not a valid 4.6 runtime API. Godot generated glTF LODs may exist, but verify actual renderer primitive counts/frame traces.

### Hardware target testing: measure, don't guess

Build two renderer APK profiles: **Vulkan Mobile** (main, modern Android) and **Compatibility GLES** (fallback), plus selectable graphics quality. Record FPS 1% low, frame time CPU/GPU, thermal behavior after sustained rounds, RAM/native heap/texture residency, draw calls, visible primitives and resolution scale. Frame pacing target 60 FPS for touch FPS feel, downgrade gracefully to stable 30 FPS on slower Android. This is a **target**, not measured output.

Use **Android GPU Inspector** frame/system profiling or its successor **Android Performance Analyzer**, real connected Android test hardware, physical gameplay camera motion, spawning zombies and HUD: 
- https://developer.android.com/agi
- https://android-developers.googleblog.com/2026/05/introducing-android-performance-analyzer.html

Until devices are profiled no claim that 'Godot limits Android' or that 'all Android can run UE5 Nanite/Lumen'; hardware and engine are distinct.
