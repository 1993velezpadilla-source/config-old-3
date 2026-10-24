# Xziel Mobile GPU-Driven Policy: Benchmark, Don't Assume

Research date: 2026-09-21

## Principle

GPU-driven rendering is powerful but is not universally faster on mobile.

Public Tencent engineering discussions identify mobile-specific risks:
- large/random storage-buffer access may spill to system memory;
- instance/primitive fetch in vertex work can be expensive;
- tile/binning architectures can execute position-related vertex work in ways that amplify data-fetch cost;
- cluster-level indirect rendering can create many tiny or instanceCount=0 subdraws;
- mobile scheduling/front-end hardware has finite capacity for queued draws.

Apex Legends Mobile independently reached a similar practical conclusion and used a CPU/uniform-based dynamic batching path rather than forcing GPUScene everywhere.

## Xziel policy

Support two valid paths.

### Compatible CPU-driven path
- BSP/PVS + CPU/SOC visibility;
- jobified visible list;
- preallocated instance buffer;
- UBO/uniform/vertex instance data;
- conventional instancing;
- minimal compute dependence.

### Advanced GPU-driven path
- persistent GPU scene;
- cluster/Hi-Z culling;
- indirect draw generation;
- SSBO/device-address data;
- Vulkan capability tier;
- optional virtual geometry.

## Selection

XzDeviceCaps establishes eligibility.
Startup/known-device benchmark selects candidate.
XzPerformanceGovernor can fall back if sustained GPU/thermal performance is worse.

Measure:
- total CPU frame;
- GPU frame;
- vertex cost;
- bandwidth;
- draw-front-end utilization if profiler exposes it;
- power/thermal trend;
- 1% frame-time tail.

Never enable GPU-driven based only on GPU model marketing tier.

## Public references

- Tencent mobile GPU architecture/performance discussion
  https://developer.cloud.tencent.com/article/2442873
- LIGHTSPEED high-performance UE5 mobile direction
  https://www.gdcvault.com/play/1034701/Innovation-Unleashed-High-Performance-UE5
- Apex Mobile study in this branch