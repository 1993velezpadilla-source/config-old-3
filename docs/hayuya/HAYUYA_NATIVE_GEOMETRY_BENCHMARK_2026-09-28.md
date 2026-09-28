# HAYUYA native-geometry benchmark — 2026-09-28

## Why this benchmark exists

A dense mesh is not automatically a high-fidelity model. The TRELLIS.2 preview-normal recovery experiment reached roughly 2M triangles but produced visibly melted facial and cloth geometry. HAYUYA now treats those preview-derived meshes as diagnostic-only and never promotes them to an AAA Hero Master.

The next benchmark therefore tests **model-generated native geometry** before density inflation.

## Hunyuan3D-2.1 probe

GitHub Actions run:

- run: `36434183500`
- workflow: `HAYUYA Hunyuan Native Probe`
- result: success

Exact native mesh telemetry:

- generator: `tencent/Hunyuan3D-2.1`
- endpoint: `/shape_generation`
- seed: `1993`
- inference steps: `30`
- octree resolution: `384`
- faces: **888,742**
- vertices: **444,231**
- connected components: **3**
- dominant component fraction: **0.999892**
- mesh gate: **PASS**
- output size: **15,996,908 bytes**

The front and face evidence rendered successfully in Blender.

## Visual conclusion

The native Hunyuan candidate is a materially better geometric base than the preview-normal reconstruction:

- coherent full-body silhouette;
- coherent layered robe volume;
- hands and sleeves are recognizable geometry;
- no catastrophic melted-surface noise;
- no 10k-component UV-seam fragmentation.

It is **not yet Tripo-quality**. The face is too generic/simple and loses the source character's identity/detail. This means HAYUYA should use Hunyuan as a native geometry challenger, not call it a finished Hero Master.

## Current policy

For High/Ultra:

1. preview reconstruction may be preserved as diagnostic/material evidence;
2. only native/model-generated or explicitly image-conditioned refined geometry can enter the AAA Judge path;
3. polygon density is telemetry, not an approval criterion;
4. semantic front + face evidence is rendered before expensive full turntable Judge;
5. a bad face fails closed;
6. source-derived head-detail fusion is tested as a separate challenger;
7. runtime retopo/LOD remains downstream from HAYUYA 3D.

## License boundary

Hunyuan3D-2.1 remains opt-in in `backends.lock.json` under the Tencent Hunyuan 3D 2.1 Community License. The current integration may benchmark and Judge its output, but sets:

- `license_review_required=true`
- `distribution_eligible=false`

Technical Judge success must not silently bypass product/distribution license review.
