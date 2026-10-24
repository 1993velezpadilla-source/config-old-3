# LifeAfter Software Occlusion Culling → Xziel Visibility Benchmark

Research date: 2026-09-21

## Public result

NetEase's GDC 2023 presentation describes an efficient software occlusion culling system used in LifeAfter.

Reported production result:
- about 1.5 ms per frame on low-end hardware represented by iPhone 6s;
- average draw-call reduction around 65%;
- no false occlusions in the reported system;
- designed for a dynamic open world.

The system combines:
- lightweight software occlusion algorithm;
- carefully organized culling pipeline;
- generated high-quality occlusion meshes;
- cache-miss reduction;
- multithreading;
- NEON-oriented optimization on supported phones;
- visibility-function-based smoothing for occluder generation.

## Xziel target

XzOcclusion should not rasterize production meshes directly unless justified. Build simplified occluder meshes offline and optimize them for conservative visibility.

Pipeline:
1. BSP/PVS or room visibility
2. frustum culling
3. projected-size culling
4. software occluder depth/raster
5. object/cluster tests
6. instance/batch construction

## Correctness rule

False occlusion is worse than missed occlusion. The system must be conservative: an uncertain object is visible.

## Initial Xziel performance gate

On representative mid/low Android hardware:
- target <= 1.5 ms for the full software-occlusion stage in stress scene;
- target >= 40% draw-call rejection before enabling by default;
- aspirational 60%+ in strongly occluded indoor scenes;
- zero known false occlusions across camera-path regression tests.

Because Xziel Zombies maps contain rooms, doors, windows and corridors, the geometry is unusually favorable for this kind of occlusion.

## Public references

- GDC 2023: Efficient Software Occlusion Culling on Mobile Platform in Life After
  https://www.gdcvault.com/play/1029042/Efficient-Software-Occlusion-Culling-on
- NetEase GDC 2023 announcement
  https://www.neteasegames.com/news/20230612/37000_1078434.html