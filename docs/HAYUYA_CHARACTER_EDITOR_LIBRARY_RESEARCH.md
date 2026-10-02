# HAYUYA Character Editor — Zombie Motion + Audio Library Research

Updated: 2026-09-23

This document defines the source/library boundary for the HAYUYA Character Editor.
The editor separates normal reusable zombie animation from **human-performed real
motion capture**, audio, facial/secondary motion and package-time add-ons.

## Library UX contract

The character editor is organized into:

1. **Zombie Animations** — local/approved reusable clips organized by Idle, Walk,
   Run/Chase, Attack, Crawler, Hit, Death, Turn/Transition and Special.
2. **Real Mocap** — human-performed motion capture kept in its own tab.
3. **Zombie Audio** — vocals, screams, attack, pain, death, footsteps and crawler/wet movement.
4. **Add-ons** — blink, jaw/mouth, eye motion, hair/cloth secondary motion,
   audio-event binding, face/texture passes and mobile optimization.
5. **Package** — selected one-tap recipe becomes a versioned ZIP saved in GitHub.

No external pack is silently treated as locally distributable. A catalog entry
must become `availability=local` only after its files and license have been
ingested and recorded.

## Already local / redistribution-safe

### Quaternius animated humanoid donor
HAYUYA currently stores a CC0 rigged/animated Quaternius humanoid donor with
embedded Idle, Walk, Run, Punch, Death, Jump and Working/restless clips.
It is the first donor for the HAYUYA AutoRig prototype and Live Preview.

### CC0 horror/zombie audio pool
The restored project audio library contains 1,106 source audio files and keeps
source provenance beside the packs. Relevant zombie/character pools include:

- artisticdude — Zombies Sound Pack (CC0)
- Darsycho — Zombie moans (CC0)
- rubberduck — CC0 creature SFX packs
- Corsica_S / qubodup — CC0 snow/gravel footsteps
- rubberduck — CC0 water/splash/slime for crawler/wet-body layers

The runtime/editor policy remains: no copied/ripped COD/Treyarch audio.

## Human-performed / real mocap research

### Rokoko — 12 free zombie animations
Source: https://www.rokoko.com/resources/rokoko-mocap-12-free-zombie-animations

Rokoko states that the 12 zombie/Halloween recordings were performed by Creative
Director Sam Lazarus and captured with Smartsuit Pro II + Smartgloves. The pack
is full-body (including finger motion), FBX, 30 FPS, Mixamo skeleton, and Rokoko
states it can be used from passion projects through commercial projects.

HAYUYA catalog status: `external_download_required`.
Do not mark one-tap-ready until the actual FBX files and source notice are ingested.

### MoCap Online — free demo / Zombie libraries
Demo: https://mocaponline.itch.io/mocap-online-demo
Animation list: https://mocaponline.com/pages/animlist/zombie-pro

The free demo contains samples from several MoCap Online libraries, including
Zombie. Their Zombie catalog is extensive and explicitly organized around
attack, hyper-attack, chase, hyper-chase, crawl, walk, stand, turn, death and
transitions. Current product pages list hundreds of clips depending on tier.

HAYUYA catalog status: demo and paid libraries remain external. Paid/current
license terms must be reviewed before ingestion; do not copy files from third-
party mirrors or unlicensed reposts.

### Vicon mocap zombie library (Fab)
Source: https://www.fab.com/listings/7559e39e-ad01-42aa-a5fb-d0f8e10f0601

Professional Vicon-captured zombie motion library with movement, attacks and hit
reactions. Catalog-only until purchased/licensed.

## CC0 expansion research

### Quaternius Universal Animation Library 2
Source: https://quaternius.com/packs/universalanimationlibrary2.html

CC0, 130+ animations, FBX/GLB/Blend, universal humanoid rig, ready for
retargeting, and explicitly includes zombie locomotion.

### Quaternius Animated Zombie Pack
Source: https://quaternius.com/packs/animatedzombie.html

CC0 zombie pack, two animated zombie models, FBX/OBJ/Blend. Candidate source for
more zombie-specific motion after ingestion.

## Additional CC0 zombie audio research

- saturn91 — Zomby SFX Pack (CC0):
  https://opengameart.org/content/zomby-sfx-pack
- ianzazz — Zombie noises and moans (CC0):
  https://opengameart.org/content/zombie-noises-and-moans
- EmoPreben — Zombie Moans 01 (CC0):
  https://opengameart.org/content/zombie-moans-01-by-emopreben
- artisticdude — Zombies Sound Pack (CC0):
  https://opengameart.org/content/zombies-sound-pack
- Darsycho — Zombie moans (CC0):
  https://opengameart.org/content/zombie-moans

## One-tap rule

"One tap" in HAYUYA means:

- clicking a local animation adds the clip to the current character recipe;
- if the current GLB already embeds that clip, the preview immediately plays it;
- otherwise the package workflow rigs/retargets the selected local library onto
  the character before export;
- audio pools are copied into the character package and event bindings are
  recorded in `character_profile.json`;
- external mocap stays unresolved until licensed/ingested;
- Save/Build generates the ZIP plus recipe/build metadata and persists it under
  `hayuya/packages/<job_id>/` in GitHub.

A package may not call itself game-ready while it contains unresolved external
mocap or missing local audio paths.
