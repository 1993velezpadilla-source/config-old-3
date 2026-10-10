# Black Pines — free CC0 hospital props, review-only

Before using paid Tripo credits, the workflow runs a 16-model **real CC0 GLB intake** and visual QA in Godot 4.6.1. The source asset pack at https://3dassets.dev/packs/hospital-wards-and-clinic-operations lists 80 models, declares CC0 1.0 Universal, and discloses AI generation. These are stylized modern-hospital assets; they are not automatically a visual match to the abandoned Black Pines aesthetic.

The workflow `.github/workflows/black-pines-original-playable-blender-gate.yml` downloads 16 selected IDs only from `https://cdn.3dassets.dev/assets/<ID>/v1/model.glb`, validates actual GLB geometry, lengths, required extensions and API CC0 declarations, and records SHA256 hashes. Candidates include a bed, IV stand, wheelchair, trolley, surgical table and equipment, fridge, reception furniture, shelving, a cleaner cart and **an ambulance for comparison**.

Artifacts: `Black-Pines-Free-CC0-16-Assets-Godot-Art-Audition`, containing the manifest, 16 **real in-engine Godot** preview images and a 4x4 contact sheet. Import into a separate stage only. **Do not yet replace existing Black Pines props, and do not ship unreviewed files in the APK.**

Final review still requires matching styles, legal provenance, collision, AI pathfinding, texture treatment and actual Android memory/FPS. Do not confuse nominal CC0 or visual preview GREEN with public-release approval.

The original map, Black Pines endless rounds, church and Nacht remain unchanged during this audition.

## Proven import compatibility (2026-10-10)

The original 16 source meshes downloaded successfully and passed source CC0,
binary GLB2, per-mesh triangle and SHA256 audits (9,964 triangles total).
**Stock Godot 4.6.1 rejected every raw GLB** because each requires
`KHR_mesh_quantization`. The source website's general claim that this
extension needs no special support in Godot did not hold for the CI build.

Fixed in `xogot/tools/cc0_dequantize_godot.py`, which decodes the exact
original signed 16-bit normalized POSITION and NORMAL data into float32
core glTF2, retaining nodes/materials/pivots, instead of hiding the
extension flag. This was validated both with offline mesh-bounds comparisons
and with **all 16 Godot imports + 16 actual screenshot renders GREEN**
([standalone workflow run](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/38068252634)).

Artifact `Black-Pines-Free-CC0-16-Real-Assets-And-Godot-Photos`
contains the unmodified original source files, dequantized Godot-compatible
copies, license hashes, 16 individual real Godot screenshots and the 4x4 sheet.

Separately, **four specific source props** — wheelchair, IV stand,
privacy screen and surgical lamp — are authored as original named
`Forge_CC0_*` meshes in Blender, with source provenance in
`xogot/data/black_pines_cc0_manifest.json`. Godot gameplay-mount
approval remains gated independently in the main Black Pines workflow.
