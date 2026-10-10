# Church Revival phase 1 — 2026-10-10

This resumes the existing playable church on `feature/church-expansion-v1`.
Black Pines work remains separate; no previous map/gameplay files are removed.

- Extend original training loop with two walkable, collision-backed courtyards,
  WestOssuaryGarden and EastPilgrimCloister; access is open and floor connectors
  overlap existing pads. Basements, upper-floor routes, eight window barricades
  and all original church geometry remain.
- Bring paid wall buys from 4 to 10. Six new existing weapon IDs use real
  World at War-derived viewmodel paths in the weapon catalog: Kar98k, Gewehr,
  PPSh, Type 100, STG-44, and FG42. Their wallet debit/equip interaction is
  exercised in the church interaction probe. New locations are visibly chalked.
- Keep all SIX already implemented original-to-this-project powered perk
  mechanics. Relocate Quick Hands and Pilgrim Rush to the new east/west
  courtyards, to encourage exploration without inventing unimplemented perks.
- Keep existing zombie AI/round logic. Current normal zombie visual is the
  project's monja asset, NOT a verified original Call of Duty zombie mesh.
  Source-model identification/import, animations, clipping and licensing still
  need separate real-runtime gates. Do not claim the original zombie port done.
- Public builds must include only independently verified rights-cleared
  models/audio/other content; files extracted from Call of Duty are not
  presumed redistributable.

This is an authored source change, NOT a claim of completed Android APK,
screen-render fidelity, collision-path navmesh coverage, or published release.
CI must parse the game and run updated interaction + expansion probes before
this phase can be marked GREEN.
