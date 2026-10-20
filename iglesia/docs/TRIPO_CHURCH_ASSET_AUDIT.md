# Iglesia Tripo — corrected recovery audit (2026-10-20)

**CORRECTION: THE OWNER'S ORIGINAL TRIPO ASSETS HAVE BEEN FOUND.**
Previous GitHub-only inspection was incomplete. The missing sources were not
imaginary and must not be redrawn.

## Authoritative Library source

Folder: `/ZOMBIESSSSSSS PORTABLE/gift_runtime_packs/` in the user's ChatGPT Library.

| ZIP | GLB models | Verified SHA-256 |
|---|---:|---|
| `altar.zip` | 9 | `427a6cd1cc5f54e4dec0fec72761872955b9d5820cd4761d48b247ea79decd5f` |
| `candleholders.zip` | 19 | `3627fcd408fdac84594edb4cc40d8c7ce28e5e580e1e6aca4878e31f7c801d6f` |
| `chandeliers.zip` | 11 | `51343ba8401df1e562a6e6b89730c05a9bb1d74f399418ddda45bd44162792d3` |
| `furniture.zip` | 12 | `2d26885f668d9bb019c0495d235888d3c1eccc92e941a97f6dc5edc8e08b5ddd` |
| `ruins.zip` | 29 | `011a889e61bbd5fc4fdbee8aa197aacfe97d15ae6e2d0425350a235bf47a7348` |
| `stained_multi.zip` | 11 | `c208d73bf2a7a2563237b8a85a49411f185322cb4c681427b375e47cc87622f5` |
| `stained_single.zip` | 1 | `37248a62c128ae8536809cd91da2c7ba3f98ea569617b323c7fa6444377f33fe` |
| `statues.zip` | 12 | `35da7f3908a8214ed3a323b21c000116e7089509452b593b9d6177c57c0c64f7` |

Verified originals: **8 ZIP, 104 individually split GLBs**, **14,986,049 triangles** total.
Each split GLB is real binary glTF and references original external texture
files inside its package's `textures/` folder (albedo, ORM, OpenGL normal).
The group names correspond to original master GLBs:
`candelabros colgantes techo.glb` (11 original roof chandeliers),
`ornate candle holder 3d model.glb` (19 holders),
`gothic church furniture 3d model.glb` (12 furniture),
`intricate wooden altar 3d model.glb` (9 altar components),
`medieval church ruins 3d model.glb` (29 ruins),
stained glass multi (11) + single (1), and statues (12).

Individual `Model_01` etc may represent components/submeshes, not a semantically
independent complete fixture. The 19 candleholder models are **not** automatically
all wall sconces. Their physical mounting must be visually verified before final placement.

## GitHub integration and source constraints

Code branch: `feature/iglesia-godot-cleanroom-20261020`.

Production import adapter: `iglesia/tools/stage_original_tripo_packs.py`.
Original archives can be staged at:
- `iglesia/source_tripo_packs/`
- `assets/tripo_packs/`
- `iglesia/original_tripo_archives/`

It SHA-verifies **all eight archives**, audits **104 model members and texture
dependencies**, retains the original ZIPs unmodified and writes a complete model
catalog in `iglesia/assets/tripo/fixtures_catalog.json`.
The *initial nave* only imports source models `chandeliers/Model_{01,03,05,07}.glb`
and `candleholders/Model_{01,03,06,08,10,12}.glb`, with authentic shared
textures and physical anchoring. Other 94 models remain accessible in their
original source archives for later rooms, not silently converted into substitutes
or stuffed into the 31m main aisle.

**Verified blocker:** These original ZIPs live in the ChatGPT Library, not in
the GitHub repository. The current GitHub connector writes source text but
does not ingest local binary ZIPs by path. Consequently, this commit integrates
the exact-source importer but does **not** make any unsupported claim that all
GLB media have been shipped to GitHub or the APK. Earlier GitHub-only
"missing files" reports should be superseded by this source audit.
