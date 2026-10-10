# Church-first playable template — original gameplay before reskin

The user-requested sequence is preserved: **Nacht der Untoten Chronicles-style
full interactive template in the EXISTING church**, first working verified
source models/animation/sounds/particles/hands/machines, then **swap ONLY
visual skins** to monjas and custom vending models. Do not restart the map.

## Source truth, 2026-10-10

The current church repository contains a **working custom zombie AI/collision
runtime** with project nun models and CMU motions; it does not contain a
verified original BO3 Zombies Chronicles zombie skeletal mesh. Present WAW
weapon viewmodel GLBs do not prove original BO3 first-person hands, perk-drink
animations, worldmodels, effects, or redistributable audio. Six church perk
backend mechanics exist, but their rendered machines are project-authored,
not actual Chronicles vending machines.

`xogot/data/church_chronicles_template.json` lists each source lane with
MISSING status until genuine source bytes and import/clip proofs exist.
Do not print "ORIGINAL GREEN" from the existing nun rig.

## Implementation this gate

- Real `CharacterBody3D` is AUTHORITATIVE for chase, health, hitzones,
  barricades, window physics, round scaling and server state.
- Optional authentic rig lane `res://assets/zombies/chronicles/*` selects a
  model **only after** explicit source proof, Skeleton3D (20+ bones),
  renderable meshes and all six actual animation clip mappings.
- Original rig is uniformly scaled against the capsule footprint; axis squash
  is forbidden so future nun retargeting preserves the authored skeleton.
- Model/skin changes cannot alter the physics capsule or gameplay director.
- CI checks actual zombie movement towards player, physical capsule, live perk
  interaction backends and truthful original source status.
- All current church assets and game systems remain unchanged.

## Explicit outstanding acceptance gates

1. Stage verified original Chronicles zombie skeletal meshes, skeleton
   hierarchy, idle/walk/attack/hit/death/crawl clips and prove attack/barricade
   animations line up with physical hits, collisions and replication.
2. Verify all original perk machine visuals, trigger windows, power/audio,
   animation and script mechanics against authored tests.
3. Verify real original weapon/hands assemblies, calibrated ADS, reload,
   exact interaction animations (including bottle/drink) and sound timing.
4. Verify original particles, audio assets and mobile resource budgets.
5. After above: author and bind the 3D nun skin to the verified skeleton in
   Blender, preserving all bone weights, UV mapping and animation behaviour.
   A PNG alone cannot convert different mesh topology into a nun.
6. Release uses only content with distribution rights/permission. A playable
   private technical audit is not automatically a redistributable public APK.

Current truthful status: template infrastructure integration only. Original
Chronicles source audit RED/PENDING, not a completed one-to-one game.
