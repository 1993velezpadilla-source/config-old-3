# Church V1 — Free Art Source Shortlist

Status: research shortlist only. No candidate is approved for shipping until its
downloaded files, embedded texture provenance, transforms, UVs, material setup
and license are audited locally.

The current procedural Main Nave prototype is only ~34,968 triangles / 10
materials. It is intentionally non-shippable and is below the Church V1 final
art minimum of 180k triangles. The purpose of this shortlist is to replace
box/proxy quality with authored source detail without sacrificing gameplay
dimensions or XZIEL runtime discipline.

## A. Best whole-interior candidate

### Old church modeling — Interior Scene — Aurélien Martel

Source:
https://sketchfab.com/3d-models/old-church-modeling-interior-scene-eb6cf543aa7d45e3acee49887ae3135c

Public listing reports:
- 306.3k triangles
- 268.9k vertices
- downloadable
- baked / UV-mapped interior
- CC Attribution
- gothic vaulted interior with stained glass and dark/horror-compatible look
- GLB/glTF conversion is also listed on Fab

Why it is interesting:
- lands directly between Church V1's 180k minimum and 450k preferred art
  targets
- much closer to the desired visual quality than the current procedural nave
- already authored as an interior rather than a facade-only cathedral
- baked look can be useful as source reference even if XZIEL rebuilds the
  materials into its own PBR/lightmap pipeline

Required audit before use:
- download original/converted files
- record exact CC attribution text and source URL
- inspect embedded image licenses/provenance
- verify that pews/altar/windows are separable or can be remeshed without
  destroying topology
- inspect UV0 and any additional UV channels
- audit tangent basis/normals
- measure true real-world scale
- detect duplicated/hidden geometry and backfaces
- test conversion into XZIEL without global decimation

## B. High-detail alternate — license dependency must be audited

### Cathedral — tabitown

Source:
https://sketchfab.com/3d-models/cathedral-f0d2480a1707407082fa18b51f7ba666

Public listing reports:
- 605.6k triangles
- 308.6k vertices
- CC Attribution
- interior cathedral study
- author states textures came from textures.com

Pros:
- within Church V1's 900k authored triangle ceiling
- strong arcade/column/vault proportions
- enough source geometry for an HQ interior

Blocker:
- do not integrate until the third-party texture license is verified. A CC-BY
  mesh listing does not automatically grant redistribution rights for every
  externally sourced texture embedded by the author.

## C. Photogrammetry alternate

### Room of an abandoned church — danard

Source:
https://sketchfab.com/3d-models/room-of-an-abandoned-church-82dd09204997496a80007f70accc3d06

Public listing reports:
- 600k triangles
- 301.1k vertices
- 127-photo photogrammetry
- CC Attribution

Use case:
- candidate source for distressed wall/stone detail or a contained side room
- do not assume it is suitable as the entire gameplay church until bounds,
  holes, collision suitability and texture dependency are audited

## D. CC0 low-risk structure / prop donor

### Medieval Church Interior — AnyRPG / BlendSwap

Source:
https://blendswap.com/blend/26456

Public listing reports:
- ~48.2k triangles
- CC0
- explorable church interior

Use case:
- donor/reference for modular church props, proportions and pieces
- not sufficient by itself for Church V1 final-art density/quality

## E. CC0 material/reference sources

Poly Haven assets are CC0 and are good candidates for rebuilding Church V1
materials at 2K rather than relying on unknown baked image provenance.

Useful sources:
- Plastered Stone Wall:
  https://polyhaven.com/a/plastered_stone_wall
- Plaster Stone Wall 01:
  https://polyhaven.com/a/plaster_stone_wall_01
- Monastery Stone Floor:
  https://polyhaven.com/a/monastery_stone_floor
- Old Wood Floor:
  https://polyhaven.com/a/old_wood_floor
- Wooden Planks:
  https://polyhaven.com/a/wooden_planks

Lighting/look references:
- Bell Tower HDRI:
  https://polyhaven.com/a/bell_tower
- Graaff Reinet Groote Kerk HDRI:
  https://polyhaven.com/a/graaff_reinet_groote_kerk
- Chapel Day HDRI:
  https://polyhaven.com/a/chapel_day

Use these HDRIs primarily as lighting/reference capture. Do not ship a huge HDR
merely because it is available at 20K/24K; Church V1 runtime should derive a
small reflection/environment representation appropriate to the Vulkan mobile
budget.

## F. Excluded / caution candidates

- Assets marked CC BY-NC: exclude from a commercial game.
- Assets with CC BY-SA: avoid as the primary map unless we deliberately accept
  the share-alike obligations for derivatives.
- Sketchfab NoAI assets: avoid feeding into AI-assisted transformation or
  analysis workflows even if direct game usage may otherwise be licensed.
- Multi-million-triangle photogrammetry is not automatically rejected, but it
  must be used selectively as a donor and audited against Church V1's 900k
  authored-map ceiling. Do not blindly decimate an entire scan and call it the
  final level.
- Exterior-only cathedral scans are not useful substitutes for a playable
  interior.

## G. Selection gate

A candidate may replace the procedural nave only after it passes:

1. license/provenance audit
2. source file opens cleanly in Blender
3. real-world scale can be normalized to the current 18 m x 30 m nave gameplay
   envelope without grotesque distortion
4. player capsule and zombie body widths still clear the critical aisles
5. collision/navigation can be authored independently from visual geometry
6. architecture can be partitioned spatially for XZIEL culling/streaming
7. UV/material/tangent audit passes
8. visual screenshots are materially better than the current prototype from
   player-height cameras, not just from a beauty render
9. no hidden dependency on a paid asset/service
10. attribution can be preserved in the shipped game when required
