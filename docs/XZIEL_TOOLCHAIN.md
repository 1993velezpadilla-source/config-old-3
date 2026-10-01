# XZIEL Content Toolchain

This branch keeps map production reproducible and commercial-safe by default.

## Automatic fast toolchain
`tools/xziel_toolchain/bootstrap_fast.sh` installs into `.xziel-tools/`:
- meshoptimizer/gltfpack v1.3
- Khronos KTX-Software v4.4.2 stable
- Recast + Detour v1.6.0
- xatlas pinned at f700c7790aaa030e794b52ba7791a05c085faf0c

These are intended for every map worker/agent.

## Deep CPU reconstruction toolchain
`tools/xziel_toolchain/bootstrap_deep_cpu.sh` installs:
- Open3D CPU 0.20.0
- pycolmap 4.2.1
- OpenCV/Pillow/Numpy

Use this for photo matching, reconstruction, point-cloud cleanup, registration, and geometric QA.

## GPU reconstruction workers
GPU-heavy systems are intentionally not installed in ordinary GitHub-hosted CPU runners. They are registered in `manifest.json` and must use commercial-safe checkpoints:
- MapAnything: use the Apache model checkpoint, never the NC checkpoint for commercial assets.
- VGGT/Omega: use a commercial-use checkpoint.
- TRELLIS.2 / TripoSG / gsplat: validate model and dependency licenses before enabling.

## Agent rule
A generated map asset is not accepted merely because a command succeeds. The worker must emit evidence: geometry fingerprint/statistics, renders, file size, and tool versions. Existing Geometry Nodes map-builder fingerprints remain authoritative for geometry-change tests.

## Commands
```bash
bash tools/xziel_toolchain/bootstrap_fast.sh
python3 tools/xziel_toolchain/doctor.py --root .xziel-tools

bash tools/xziel_toolchain/bootstrap_deep_cpu.sh
python3 tools/xziel_toolchain/doctor.py --root .xziel-tools --deep

bash tools/xziel_toolchain/optimize_glb.sh input.glb output.glb
```


## Geometry CPU toolchain
`tools/xziel_toolchain/bootstrap_geometry_cpu.sh` installs a small collision/mesh environment:
- trimesh 5.1.0
- CoACD 1.0.14
- manifold3d 3.5.4

`generate_collision_hulls.py` converts an existing triangulated collision GLB into separate convex hull meshes and a JSON evidence report. The generated hull GLB is a sidecar candidate; existing fitted collision stays available until the XZIEL runtime loader is explicitly wired to consume the hull set.
