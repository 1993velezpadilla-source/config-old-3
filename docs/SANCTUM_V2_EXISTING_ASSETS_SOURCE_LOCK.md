# SANCTUM V2 — EXISTING-ASSETS-ONLY SOURCE LOCK

This branch intentionally abandons the previous St Giles / Sanctum pipeline.

## Hard exclusions

The Sanctum V2 build on this branch MUST NOT consume, import, derive from, or call:

- `.github/workflows/church-map-blender.yml`
- `sanctum_harness.bsp` / `sanctum_harness.nsz`
- the previous St Giles Cripplegate GLB
- `church_zombies_gameplay_v1.blend`
- `church_runtime_fitted_v2.json`
- the previous `sanctum.xzsm`
- any old church geometry, collision, nav, texture atlas, or dressing artifact

Old files may remain elsewhere in the repository for history, but this branch's new pipeline must not reference them.

## Source policy

No custom procedural church geometry is authored for the first visual pass.

The first pass must be assembled from existing third-party Blender systems/assets that already contain authored architectural generators. Custom code may only orchestrate, inspect, render, export, validate, or connect those existing systems.

### Primary existing source

IRCSS / Blender-Geometry-Node-French-Houses
- License: MIT
- Upstream: https://github.com/IRCSS/Blender-Geometry-Node-French-Houses
- Primary asset file: `GeometryNodesFrenchHous.blend`
- Existing generators documented upstream include:
  - `ChurchA-Front`
  - `GenerateChurchBuildingB`
  - `ChurchFrontTowers`
  - `Generate Cathedral Combined`
  - gothic support beams
  - window systems
  - curved doors
  - stairs
  - towers

This is the first visual authority because the church/cathedral forms already exist in the upstream authored Geometry Nodes file.

### Secondary existing sources

p-schulz / osm_building_grammar
- License: Apache-2.0
- Upstream: https://github.com/p-schulz/osm_building_grammar
- Existing presets include `gothic_church` and `cathedral_stone`.

ranjian0 / building_tools
- License: MIT
- Upstream: https://github.com/ranjian0/building_tools
- Existing building tools include floors, doors, windows, roofs, stairs, balconies.

### Deferred source

Aniruddhyagoswami / arch_generator is GPL-3.0-or-later.
It may be evaluated as an external build-time tool, but its source is NOT vendored into XZIEL on this branch until distribution/license implications are explicitly reviewed.

## Acceptance rule

No source is accepted because a script says GREEN.

A candidate must produce visible rendered evidence. The first audit renders existing church/cathedral/gothic objects from the upstream Blender file without authoring replacement church geometry.

The next stage may compose accepted existing generators into a new playable layout, but the geometry-producing systems themselves must remain upstream-authored and source-attributed.
