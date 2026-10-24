# Rock Kingdom World → Xziel Tile-Memory / Pass-Fusion Study

Research date: 2026-09-21

## Why it matters

Rock Kingdom World is based on UE4.26 mobile forward rendering and publicly documents deep modifications aimed specifically at tile-based mobile GPUs.

## Avoid expensive CustomDepth when a cheaper classification works

In the described project, a separate CustomDepth/Stencil path could add an extra pass, render-target bandwidth and very large draw-call multiplication for many characters.

The team instead used RGB10A2 scene-color alpha as an inexpensive per-pixel character/scene classification channel written during BasePass. Encoding/decoding extends useful HDR range and a nonlinear sqrt-style encoding protects precision near black.

Xziel lesson: do not allocate a whole buffer/pass when a few existing bits/channels can safely carry the semantic data.

## Framebuffer Fetch / SubPass post processing

For post effects that only need the current pixel, the project uses framebuffer fetch/subpass-style access instead of sampling a separate resolved scene-color texture.

Public stress-test numbers cited in the technical write-up:
- bandwidth reduced about 23%;
- GPU time reduced about 31.6%.

In a real-game scene the reported gains were smaller but still meaningful:
- GPU time about -5.5%;
- total bandwidth about -12.8%;
- read bandwidth about -16.5%.

## Pass fusion

The pipeline merged multiple effects/passes and reduced a described configuration from five render passes / four intermediate memory write-backs to two passes / one write-back.

This is exactly why XzRenderGraph must know:
- attachment lifetime;
- whether a resource is transient;
- whether current-pixel framebuffer/depth fetch is enough;
- which neighboring-pixel effects prevent fusion.

## Ultra-cheap Deferred HDR path

The team also describes a Deferred-HDR-style path keeping work from PrePass through ToneMapping inside one RenderPass/tile-memory-oriented flow by dropping effects requiring neighborhood samples such as SSAO/SSR/Bloom while retaining high-impact effects such as fog, color grading and tonemapping.

This should inspire a Xziel low-power HDR tier, not replace the main renderer blindly.

## Xziel RenderGraph heuristic

Every pass should declare:
- readsCurrentPixelOnly;
- needsNeighborhood;
- needsHistory;
- canFramebufferFetch;
- canMemoryless;
- canFuseWithPrevious;
- mustPersistAfterPass.

Then backend/device capabilities decide fusion.

## Public reference

- GameRes / UF2025 Shanghai technical write-up
  https://www.gameres.com/916723.html