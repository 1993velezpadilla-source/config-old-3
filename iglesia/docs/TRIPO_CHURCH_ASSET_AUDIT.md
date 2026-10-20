# IGLESIA — original Tripo church assets audit (2026-10-20)

**Authority:** `feature/iglesia-godot-cleanroom-20261020` — clean-room Godot 4.6 project. Previous map/gameplay scripts must NOT be imported.

## Verified present in owner GitHub
- `xogot/assets/environment/church/altar.glb` — 69,805,480 bytes; pinned blob SHA `30516ffc82687374793e555fbe66f6f4b325e206`.
- `xogot/assets/environment/church/bench.glb` — 70,099,048 bytes; pinned blob SHA `12fff5499483ce023803f4460e0b52190d2799be`.
- `xogot/assets/environment/church/church_final_architecture.glb` — 8,905,540 bytes, generated geometry and **not a Tripo chandelier**.

A search of the main owner repositories and multiple Oct 19/20 church feature branches identified no tracked GLB with original Tripo chandelier, ceiling lantern, wall sconce, or candelabra source. The above two original furniture assets already stage into Iglesia, but no fixture can truthfully be called integrated yet.

## Automatic source inventory, no substitutions
`iglesia/tools/stage_tripo_fixtures.py` checks:
- `xogot/assets/environment/church`, `xogot/assets/church`
- `assets/tripo/church`, `assets/tripo3d/church`, `xogot/assets/tripo`
- `iglesia/source_tripo`

For matching fixture-model filenames/folders, stage exact GLB bytes, validate glTF container signature, deduplicate by Git blob hash, and record every asset origin in `iglesia/assets/tripo/fixtures_catalog.json`. Unclassified GLBs are separately reported and **never** randomly inserted.

Godot maps each verified staged fixture model at least once, fitting model bounds to source-safe sizes and snapping to actual ceiling underside (Y=8.29), wall interiors (X=±8.25), or floor (Y=0.02). No floating placeholder chandelier, no generated illustration, no CC0 substitution, no copy of the rejected gun or hands.

**Blocker:** The chandelier/sconce Tripo exports appear not to have been committed to the GitHub source folders inspected. Uploading the originals to one of the checked folders makes them discoverable by the existing GitHub Actions staging pipeline. The current test must print `IGLESIA_TRIPO_CHANDELIERS_NOT_IN_GITHUB_YET` until it has real fixture source material.
