# XZIEL BO3-style complete map loader audit — v1

## Goal

Make a verified XZIEL map package behave like a complete game zone rather than
"a BSP plus whichever files happen to be referenced first". The target is
zero-omission activation: a map is promoted only when its declared runtime
families are present, dependency-resolved, mounted, preflight-visible, and each
runtime subsystem reaches its own ready gate.

This design borrows the public architectural principles exposed by Black Ops III
Mod Tools and community documentation. It does not copy proprietary engine code.

## What BO3's public mod pipeline reveals

BO3 Mod Tools expose a zone-oriented content pipeline:

- A map/mod zone explicitly declares asset types such as scripts, xmodels,
  images, FX, sounds, weapons, stringtables and other runtime resources.
- Linking resolves those declarations into loadable zone/fastfile content.
- Script dependencies are explicit through #using/#insert and precache calls.
- Zombies is initialized as a set of systems, not one monolithic map script:
  zone manager, spawners, weapons, powerups, perks, audio, interactions,
  player/game logic, UI/client fields, etc.
- Sound has an explicit zone configuration/alias layer and can choose loaded
  versus streamed storage.
- Runtime map zones activate adjacency/pathing/spawn logic as gameplay opens
  areas.
- Missing linked assets are treated as build/runtime defects; community reports
  show that absent materials or sound-zone entries can produce dark lighting,
  missing sounds, linker errors or broken maps.

Useful public references:
- TreyarchGames/ModLauncher (official BO3 Mod Tools launcher source)
- Official Steam BO3 Mod Tools workshop guide
- zeroy99/bo3_modtools public script mirror
- BO3-Docs / ren.gay documentation
- ZoneTool documentation for the long-standing CoD zone/fastfile asset model

## Architectural inference

The important behavior for XZIEL is not the exact BO3 binary format. It is the
lifecycle:

1. **Declare the complete map asset universe.**
2. **Resolve dependencies before activation.**
3. **Classify residency policy** (boot-loaded, world-loaded, streamed,
   on-demand).
4. **Mount one coherent map namespace.**
5. **Preflight every declared runtime artifact.**
6. **Initialize subsystems in dependency order.**
7. **Do not expose gameplay until mandatory gates are ready.**
8. **Stream optional/high-volume resources after the core world is safe.**
9. **Fail closed on missing or unsupported assets; no silent substitutes.**
10. **Keep runtime diagnostics per family so one missing category is obvious.**

## XZIEL current state before this audit

Strong pieces already existed:

- deterministic folder/ZIP inventory;
- SHA-256 verification and unsafe-path rejection;
- .xzp installation to a private atomic directory;
- 24-family zero-omission content contract;
- xziel.runtime.json promotion contract;
- strict missing-model and missing-SFX mode;
- verified package mounted through Vril's native -game search path;
- static-scene runtime with XZSC/XZMS, materials, normals, PBR scalars,
  lightmaps, reflection capture, lights and fog;
- stream residency/governor infrastructure;
- Nacht-specific gameplay and weapon reference data.

Main gap: package verification proved that artifacts existed in the ZIP, but the
native runtime did not prove that all declared artifacts were visible through
the *mounted VFS* before promoting the map. Runtime loading was also split across
specialized paths without a common package boot state.

## Universal boot phases

XZIEL package boot now uses these phases.

### Phase 1 — world core
- world_geometry
- collision
- navigation_pathing

Gate: world identity, collision and traversal data are visible before gameplay.

### Phase 2 — render world
- materials_textures
- static_models_props
- lighting_postfx
- vfx_particles

Gate: visible world dependencies are present before renderer cutover.

### Phase 3 — animation world
- animated_models_rigs
- animations

Gate: skeleton/animation resources exist before animated actors become active.

### Phase 4 — gameplay database
- weapons_equipment
- pack_a_punch_variants
- gameplay_scripts
- interactables
- perks_wunderfizz
- powerups
- gobblegum
- mystery_box
- spawns_rounds_ai

Gate: gameplay database is complete before a round can start.

### Phase 5 — audio world
- audio_sfx
- ambient_music_vo

Gate: audio aliases/banks/resources are visible before audible gameplay.

### Phase 6 — player surface and network
- hud_ui_prompts
- multiplayer_replication

Gate: UI and authoritative shared-state contract exist before multiplayer start.

### Phase 7 — package/release contract
- platform_packaging
- soak_release_quality

Gate: platform package and validation evidence remain part of the promoted map
contract rather than being treated as external notes.

## Implemented in feature/xziel-bo3-style-map-loader-v1

### Generated boot plan
The Android installer synthesizes a deterministic .xziel-boot.plan from the
already-validated xziel.runtime.json. Source packages are forbidden from
supplying that generated path themselves.

Plan format:
- XZBP1 header
- one F row per required family with boot phase and declared artifact count
- one A row per runtime artifact

The plan contains all 24 required families and every declared runtime artifact.

### Native VFS preflight
The new xz_package_boot module:
- loads .xziel-boot.plan through the same Vril VFS used by the game;
- validates path safety and family coverage;
- opens every runtime artifact through VFS;
- counts visible/missing artifacts per family;
- fails on duplicate/unknown/malformed family data;
- marks READY only when all 24 families and every artifact are visible.

### Promotion gate
XzAndroidRuntime_SetVerifiedMapPackageMode now promotes a package only when:
- Android .xzp verification succeeded; and
- native VFS package preflight succeeded.

This closes the old gap where a ZIP could be correct but a mount/search-path or
case/path problem could still make runtime assets invisible.

## Next implementation layers

The VFS preflight is the database/mount gate. Full BO3-style behavior still
requires each family to own an execution gate:

- collision loader ready
- nav/path graph ready
- animation/skeleton registry ready
- gameplay script/module registry ready
- weapon/item database ready
- audio alias/bank registry ready
- FX registry ready
- HUD/LUI-equivalent binding ready
- replication schema ready

The global activation barrier should become:

PACKAGE_VISIBLE
&& WORLD_CORE_READY
&& RENDER_READY
&& ANIMATION_READY
&& GAMEPLAY_READY
&& AUDIO_READY
&& UI_NETWORK_READY

Only after that may XZIEL expose MATCH_READY / ROUND_START.

## Streaming policy

"Load the complete map" must not mean pin every byte in RAM/GPU simultaneously.
BO3's public sound tooling itself distinguishes loaded and streamed resources.
XZIEL should preserve original/full-quality source assets while controlling
residency:

- boot-critical metadata and gameplay definitions: pinned
- current-cell geometry/material descriptors: resident
- textures/lightmaps: streamed with authored resolution preserved
- audio: loaded or streamed according to package policy
- animation clips: hot-set resident, cold-set streamed
- remote cells/props: file-backed and prefetched
- no destructive automatic texture/geometry downscale

This matches the project's full-quality Nacht rule: optimization happens through
streaming, residency, batching, culling and scheduling, not asset destruction.

## Zero-omission rule

A complete XZIEL map is not READY merely because it renders a first frame.
The final definition is:

- all declared files hash-verified;
- all 24 runtime families promoted;
- all runtime artifacts VFS-visible;
- all required subsystem gates ready;
- zero missing asset fallbacks;
- world/render/audio/gameplay/network state internally consistent;
- first frame + playable frame + multiplayer validation green.

That is the architecture target for Nacht and future imported maps.
