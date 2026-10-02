# Xziel Horror Audio Source Manifest

This manifest defines the reusable horror/undead/ambience source pool for Xziel.

## Policy

- Ship only audio whose redistribution license is explicit and compatible with the project.
- Call of Duty / Treyarch audio rips, fan reposts, YouTube extractions, and other unlicensed game audio are **reference-only** and must not be committed.
- Prefer CC0/public-domain sources for the raw reusable pool.
- Keep source provenance beside every imported pack.
- Raw source files are not automatically approved for runtime use. Runtime banks should be curated, normalized, trimmed, categorized, and tested in-engine.

## CC0 source packs selected for ingestion

| Pack | Creator | License | Declared contents | Source |
|---|---|---:|---:|---|
| Zombies Sound Pack | artisticdude | CC0 | 24 WAV zombie vocals | https://opengameart.org/content/zombies-sound-pack |
| 80 CC0 creature SFX | rubberduck | CC0 | 80 creature/monster vocals | https://opengameart.org/content/80-cc0-creature-sfx |
| 80 CC0 creature SFX #2 | rubberduck | CC0 | 80 creature/monster vocals | https://opengameart.org/content/80-cc0-creture-sfx-2 |
| 80 CC0 RPG SFX | rubberduck | CC0 | 80 SFX incl. 22 creature + chain/wood/stone | https://opengameart.org/node/86018 |
| 100 CC0 metal and wood SFX | rubberduck | CC0 | 100 door/wood/metal/break/squeak impacts | https://opengameart.org/content/100-cc0-metal-and-wood-sfx |
| 100 CC0 SFX | rubberduck | CC0 | 100 doors/glass/metal/wood/springs/etc. | https://opengameart.org/content/100-cc0-sfx |
| 100 CC0 SFX #2 | rubberduck | CC0 | 100 ambient/door/footstep/thunder/wood/etc. | https://opengameart.org/content/100-cc0-sfx-2 |
| 75 CC0 breaking/falling/hit SFX | rubberduck | CC0 | 75 wood/metal/glass/stone destruction sounds | https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx |
| 30 CC0 SFX loops | rubberduck | CC0 | 30 ambient/rain/machine/water/weird loops | https://opengameart.org/content/30-cc0-sfx-loops |
| 40 CC0 water/splash/slime SFX | rubberduck | CC0 | 40 wet/slime/rain/water sounds | https://opengameart.org/content/40-cc0-water-splash-slime-sfx |
| 30 weird CC0 SFX | rubberduck | CC0 | 30 abstract/weird source sounds | https://opengameart.org/content/30-weird-cc0-sfx |
| Horror Hit Soundpack 1 | psychhead_ | CC0 | 55 horror hits/stingers | https://opengameart.org/content/horror-hit-soundpack-1 |
| 202 More Sound Effects | OwlishMedia | CC0 | 202 household/door/lock/cloth/key/etc. sounds | https://opengameart.org/content/202-more-sound-effects |
| 42 Snow and Gravel Footsteps | Corsica_S / qubodup | CC0 | 42 snow/gravel steps | https://opengameart.org/content/42-snow-and-gravel-footsteps |
| 41 snow shoe steps | Corsica_S / qubodup | CC0 | 41 footsteps | https://opengameart.org/content/41-snow-shoe-steps |

The declared counts above already exceed one thousand individual source sounds before additional standalone ambience and zombie packs are added.

## Xziel runtime categories

Raw files should later be curated into these banks:

- `undead/idle_near`
- `undead/idle_far`
- `undead/attack`
- `undead/pain`
- `undead/death`
- `undead/crawler`
- `undead/breath_gurgle`
- `world/wood_creak`
- `world/wood_break`
- `world/barricade_plank`
- `world/door_old_wood`
- `world/metal`
- `world/glass`
- `world/footsteps_wood`
- `world/footsteps_stone`
- `world/footsteps_gravel`
- `weather/rain`
- `weather/thunder`
- `weather/wind`
- `ambience/roomtone`
- `ambience/low_drones`
- `ambience/random_one_shots`
- `horror/stingers`
- `horror/ghostly`
- `horror/ritual`

## Horror-direction rules

The goal is not constant noise. Xziel should preserve the classic survival-horror tension curve:

1. Quiet base bed / room tone.
2. Sparse, randomized positional one-shots.
3. Off-screen undead vocal cues with distance filtering.
4. Material-specific footsteps, doors, barricades, windows and debris.
5. Weather layers that react to interior/exterior space.
6. Rare stingers, not repetitive jump-scare spam.
7. Round intensity raises density and proximity, not just master volume.
8. Silence remains an intentional part of the mix.

## COD/Treyarch reference boundary

The game may study Call of Duty Zombies for pacing, categories, spatial behavior, mix density, and horror direction. It must not ship copied/ripped Treyarch/Activision audio unless a separate explicit redistribution license is obtained.
