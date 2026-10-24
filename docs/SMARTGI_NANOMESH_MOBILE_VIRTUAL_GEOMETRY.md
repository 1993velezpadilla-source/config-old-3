# SmartGI / NanoMesh → Xziel Mobile Virtual Geometry Study

Research date: 2026-09-21

## Why it matters

Tencent and Arm publicly demonstrated NanoMesh as an adaptive seamless-LOD / virtual-geometry direction for cross-platform mobile rendering.

Arm reports a technology demo with scene complexity exceeding 140 million triangles rendered at nearly 120 FPS on 2023 flagship smartphones.

## Cluster-based geometry

Core direction:
- preprocess meshes into geometry clusters;
- select/cull clusters rather than only whole meshes;
- stream/choose detail continuously;
- avoid rigid dependence on artist-authored LOD0/1/2/3 transitions.

NanoMesh's adaptive culling/LOD policy also considers power consumption and camera conditions, reinforcing Xziel's decision to make quality budget-aware rather than purely distance-based.

## Storage benefit

Arm's public example compares a traditional LOD package around 1.8 GB with a NanoMesh representation around 557 MB, roughly a 70% reduction in that cited test. Pure mesh data is reported as a much smaller fraction of total storage while preserving comparable visual quality.

Do not assume Xziel will reproduce those exact ratios; use them as evidence that cluster geometry can improve both runtime work and content footprint.

## Xziel proposed XzClusterGeometry

Offline:
- build triangle clusters;
- compute bounds/cones/importance;
- construct hierarchy;
- quantize cluster data where safe;
- calculate perceptual/geometric error;
- create stream pages.

Runtime:
- BSP/PVS first;
- room/cell visibility;
- object/cluster hierarchy;
- screen/error/power budget;
- choose resident cluster detail;
- batch/submit.

## Relationship with XzPerceptualCooker

XzPerceptualCooker decides how much visual error is acceptable.
XzClusterGeometry supplies the runtime geometry choices.
XzPerformanceGovernor supplies the global budget.
XzFeaturePlanner determines where that budget has the most perceptual/gameplay value.

## Public references

- Arm: NanoMesh on Mobile
  https://developer.arm.com/community/arm-community-blogs/b/mobile-graphics-and-gaming-blog/posts/nanomesh-on-mobile
- Tencent GDC 2024 summary
  https://www.tencent.com/tencent-games-shares-insights-and-technologies-at-gdc-2024/