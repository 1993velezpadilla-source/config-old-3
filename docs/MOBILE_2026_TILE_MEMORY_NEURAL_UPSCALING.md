# 2026 Mobile Rendering → Tile Memory, Temporal Upscaling and Neural Paths

Research date: 2026-09-21

## Why this is important

By 2026 mobile AAA engineering is explicitly optimizing around on-chip tile memory, temporal/neural reconstruction and hardware-aware feature scaling. Xziel should expose these as optional backend capabilities instead of baking a 2023-era renderer permanently into its architecture.

## Qualcomm Adreno HPM / Tile Memory Heap

Qualcomm's 2026 Vulkan material exposes Adreno High Performance Memory through VK_QCOM_tile_memory_heap on supporting devices.

Key properties:
- high-speed GPU-local/on-chip-oriented memory;
- best suited to transient resources with lifetime inside a submission scope;
- resources can be discarded when no longer needed;
- keeping deferred attachments/local intermediates out of system memory can reduce bandwidth.

XzRenderGraph should therefore classify transient tile-local candidates explicitly.

Proposed flags:
- transient;
- tileLocalPreferred;
- preserveAfterPass;
- memorylessAllowed;
- fallbackSystemMemory.

## Neverness to Everness

Qualcomm's GDC 2026 recap describes work aligning UE5 mobile rendering with Adreno tiled architecture, including Tile Memory Heap integration, render-pass optimization, AFME2, SGSR2 and adaptive game configuration for frame stability and power scalability.

Xziel takeaway: the RHI/RenderGraph must expose hardware-memory capabilities without making them mandatory.

## Arm Accuracy Super Resolution

Arm's August 2026 developer material provides a generic-library integration path specifically for custom engines.

Arm ASR is a mobile-optimized temporal upscaler derived from the FSR2 family and expects standard temporal inputs such as motion vectors plus renderer resources.

Therefore build a vendor-neutral interface:

XzTemporalUpscaler:
- input color;
- depth;
- motion vectors;
- exposure;
- jitter;
- reactive/transparency mask where supported;
- output resolution;
- quality preset.

Backends can include:
- simple spatial fallback;
- Xziel temporal fallback;
- Arm ASR;
- Snapdragon/SGSR-family path;
- future hardware/neural path.

## Qualcomm Adreno Neural Fusion (September 2026)

Qualcomm announced Adreno Neural Fusion on September 2, 2026. Public material describes:
- neural processing integrated into the graphics pipeline;
- AI super resolution;
- frame generation;
- dedicated Adreno matrix cores;
- 18 MB Adreno High Performance Memory on the referenced next-generation architecture;
- Unity and Unreal integration.

This is too vendor/new-generation-specific to be a baseline Xziel dependency.

But it proves our renderer needs an extensible reconstruction API instead of hardcoding one upscaler.

## Correct Xziel hierarchy

Baseline:
- native rendering always functional;
- dynamic resolution;
- spatial fallback.

Modern:
- temporal upscaling using XzTemporalUpscaler.

Vendor acceleration:
- selected at runtime only when supported and validated.

Neural/frame-generation:
- Ultra/experimental;
- must not modify authoritative simulation/input latency;
- HUD can be composited separately if necessary;
- automatic disable on visual artifacts, thermal pressure or unsupported motion data.

## Public references

- Qualcomm: Improving memory bandwidth with Tile Memory Heap for Vulkan
  https://www.qualcomm.com/developer/blog/2026/05/high-performance-memory-extension-optimize-memory
- Qualcomm GDC 2026 recap
  https://www.qualcomm.com/developer/blog/2026/05/snapdragon-game-studios-developer-forum-gdc-2026-recap
- Qualcomm: Adreno Neural Fusion, Sep 2 2026
  https://www.qualcomm.com/news/onq/2026/09/adreno-neural-fusion-ai-rendering
- Arm ASR custom-engine integration
  https://learn.arm.com/learning-paths/mobile-graphics-and-gaming/get-started-with-arm-asr/04-generic_library/