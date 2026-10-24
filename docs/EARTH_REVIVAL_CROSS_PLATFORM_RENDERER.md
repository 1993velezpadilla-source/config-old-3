# Earth: Revival → Xziel Cross-Platform Renderer Study

Research date: 2026-09-21

## Why this title matters

Earth: Revival is a PC/mobile open-world TPS built on a deeply customized Unity engine. Nuverse's GDC 2023 engine talk explicitly identifies a unified, highly scalable cross-platform renderer with hybrid occlusion culling, a new multi-threaded rendering architecture, a tile-based deferred renderer and a render graph dedicated to cross-platform optimization.

This is strong independent validation of the Xziel architecture emerging from the other studies.

## Core lessons

### RenderGraph must own passes and resources
Xziel should not let individual effects manually create arbitrary render targets and lifetime rules. XzRenderGraph should describe reads, writes, transient resources, attachment lifetime and execution dependencies so backends can optimize GLES3/Vulkan differently.

### Cross-platform shader semantics
Earth: Revival's public talk emphasizes write-once cross-platform shaders and passes. Xziel should separate semantic material/pass code from backend-specific compilation and capability fallbacks.

### Tile-based deferred can be valid on mobile
The game uses a tile-based deferred renderer as part of a mobile/PC scalable architecture. Together with Wuthering Waves and Delta Force, this proves that deferred should remain an optional capability path in Xziel rather than being permanently excluded.

Use it only when:
- device tile memory/bandwidth behavior is favorable;
- the lighting/material complexity benefits from it;
- RenderGraph can keep attachments transient/on-chip;
- profiling beats Forward/Forward+ on the actual device.

### Multithreaded rendering
Xziel should ultimately separate authoritative gameplay, presentation extraction, render preparation and RHI submission. A modern renderer should not block Vril gameplay while constructing every draw.

### Hybrid occlusion
Earth: Revival independently confirms hybrid visibility strategies for large worlds. Xziel should combine BSP/PVS, room cells, frustum, software occlusion and mesh-cluster culling rather than betting on one visibility system.

## Terrain blending note

A technique attributed to the Earth: Revival GDC presentation renders terrain again in a transparent stage with stencil/depth information to improve terrain-object blending without allocating a dedicated extra blend texture. The exact implementation should be treated as a reference pattern, not copied verbatim.

## Xziel implementation impact

Add/strengthen:
- XzRenderGraph as a first-class subsystem;
- pass/resource dependency declarations;
- transient render-target pool;
- capability-driven Forward vs Deferred experimentation;
- multithreaded render preparation;
- shared shader semantic layer;
- hybrid visibility integration.

## Public references

- GDC 2023: Cross-Platform Mobile and PC Rendering in Earth: Revival
  https://www.gdcvault.com/play/1029016/Cross-Platform-Mobile-and-PC
- Nuverse/press material describing the rendering talk
  https://www.4gamer.net/games/651/G065105/20230320110/

## Clean-room rule

No proprietary Earth: Revival source/assets are needed. This document uses publicly disclosed architecture as design input.