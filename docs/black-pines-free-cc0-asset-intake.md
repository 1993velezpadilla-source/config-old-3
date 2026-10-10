# Black Pines — free CC0 hospital props, review-only

Before using paid Tripo credits, the workflow runs a 16-model **real CC0 GLB intake** and visual QA in Godot 4.6.1. The source asset pack at https://3dassets.dev/packs/hospital-wards-and-clinic-operations lists 80 models, declares CC0 1.0 Universal, and discloses AI generation. These are stylized modern-hospital assets; they are not automatically a visual match to the abandoned Black Pines aesthetic.

The workflow `.github/workflows/black-pines-original-playable-blender-gate.yml` downloads 16 selected IDs only from `https://cdn.3dassets.dev/assets/<ID>/v1/model.glb`, validates actual GLB geometry, lengths, required extensions and API CC0 declarations, and records SHA256 hashes. Candidates include a bed, IV stand, wheelchair, trolley, surgical table and equipment, fridge, reception furniture, shelving, a cleaner cart and **an ambulance for comparison**.

Artifacts: `Black-Pines-Free-CC0-16-Assets-Godot-Art-Audition`, containing the manifest, 16 **real in-engine Godot** preview images and a 4x4 contact sheet. Import into a separate stage only. **Do not yet replace existing Black Pines props, and do not ship unreviewed files in the APK.**

Final review still requires matching styles, legal provenance, collision, AI pathfinding, texture treatment and actual Android memory/FPS. Do not confuse nominal CC0 or visual preview GREEN with public-release approval.

The original map, Black Pines endless rounds, church and Nacht remain unchanged during this audition.
