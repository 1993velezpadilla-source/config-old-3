# Tencent CROS / Digital Great Wall → Xziel Next-Gen Engine Study

Research date: 2026-09-21

## Public architecture

Tencent's CROS in-house engine presentation describes a lightweight/modular engine foundation containing ECS, Job System, Frame Graph and Streaming, with higher layers for Deferred+, SmartGI, virtual geometry, virtual texture/UDIM, hybrid shadows, atmosphere, HDR grading, FSR2.x, runtime PCG and offline occlusion/lighting tools.

## Frame Graph

The public slides explicitly list:
- runtime visualization;
- SubPass support;
- Tile Memory management;
- temporary-resource lifetime extension.

This strongly validates XzRenderGraph as a central architecture component rather than a convenience wrapper.

## Virtual geometry

The Digital Great Wall case cites roughly 200 million triangles and a Nanite-Lite-style solution using GPU-driven rendering, cluster quantization and cluster Hi-Z culling.

Xziel should not attempt that feature first, but the design reinforces XzClusterGeometry:
- mesh clusters;
- hierarchy;
- compact/quantized payloads;
- cluster visibility;
- streamed detail.

## Virtual textures / UDIM

The presentation describes nearly 2,000 8K source textures totaling roughly 370 GB of raw data, converted into a much smaller engine representation using UDIM/Virtual Texture techniques.

Xziel maps are smaller, but the lesson remains: source-asset resolution and runtime residency must be decoupled.

## Vegetation / scene culling

For a 250,000-piece vegetation example, CROS uses CPU+GPU hierarchical culling, GPU Scene and GPU-driven draw/LOD selection.

This belongs in Xziel's advanced tier after the compatible CPU/instance path is stable.

## Hybrid shadows

CROS combines multiple methods by spatial role rather than demanding one shadow technique everywhere:
- close: accurate CSM/VSM-style shadows;
- medium/long range: screen-space shadow contribution;
- off-screen/far complement: heightfield-like shadow data.

Xziel can apply the same principle at a smaller scale: nearest threats get expensive shadows, room/world context uses baked/cached approximations.

## Deferred+ / many lights

CROS presents a GPU-driven Deferred+ solution aimed at extremely high dynamic-light counts. Xziel does not need tens of thousands of lights, but the lesson is useful: the renderer should cluster/cull light influence before shading and never loop every light across every object.

## GI

Public slides describe hybrid GI components including screen-space lighting, surface cache, surfels/voxelized scene, screen probes and hardware-RT/SDF/Hi-Z style tracing, with scalability across platforms.

Xziel should remain simpler: baked lightmaps + sparse probes baseline; SSR/GTAO/high-tier RT only where useful.

## Public references

- GDC 2023: Building A Digital Great Wall with A New Game Engine
  https://www.gdcvault.com/play/1028729/Tencent-Games-Developer-Summit-Building
- Public GDC slide deck
  https://media.gdcvault.com/gdc2023/Slides/Bui_Yingpeng_ZHANG.pdf