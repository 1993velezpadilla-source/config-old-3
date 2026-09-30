# XZIEL Church V1 — production spec

Church V1 is the first original XZIEL Zombies church map. It does not reuse the Sanctum/St Giles scan as final geometry.

Production rule: blockout is disposable; final visible geometry must be authored 3D art with real materials.

## Tool split
- Image generation: visual target/reference only.
- Blender + authored source: architecture, modular kit, UVs, bevels, hero props, dressing, lighting previews and GLB export.
- HAYUYA: candidate generator/processor for selected props/characters; generated assets still require art review.
- Python/trimesh/Blender validation: dimensions, pivots, counts, collision proxies, metadata and quality gates.
- XZIEL/Vril: renderer, collision, nav, gameplay and Android runtime.
- GitHub Actions: reproducible builds, screenshots and artifacts.

## Zones
1. Spawn Chapel
2. Main Nave
3. Sacristy
4. Graveyard
5. Utility Basement / Power
6. Crypt / Pack-a-Punch
7. Bell Tower

The Main Nave is the first hero room that must reach final visual quality.

## Blockout pass
tools/church_v1/build_blockout.py may use cubes and proxy routes only for scale, movement, sightlines and combat flow.
The output is tagged BLOCKOUT_ONLY and shippingAllowed=false.

## Final-art pass
Final source lives under church_v1/source/church_final.glb and must be built from an authored modular kit with PBR materials, hero props, surface variation, damage, decals and lighting.

## Quality gate
tools/church_v1/validate_final_art.py rejects blockout-tagged objects, implausibly low geometry density, weak material diversity and insufficient image-backed materials.

Automated checks do not prove beauty. Final review compares three images for each hero area: target reference, Blender player-eye render and XZIEL Android player-eye capture.

## Non-negotiable
No procedural cube-built church is allowed to become the shipped visual map.