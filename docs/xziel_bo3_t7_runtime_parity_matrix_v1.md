# XZIEL ↔ BO3/T7 runtime parity audit

Status vocabulary:
- VERIFIED-T7: directly supported by public T7 reversing/mod-tool code.
- VERIFIED-XZIEL: implemented in this repository.
- PARTIAL: present but not yet equivalent in lifecycle/coverage.
- MISSING: no dedicated XZIEL runtime subsystem/gate yet.
- INFERRED: architecture inferred from public behavior/history, not claimed exact T7 internals.

## Database / zone layer

| Capability | BO3/T7 evidence | XZIEL status |
|---|---|---|
| Explicit zone load API | DB_LoadXAssets(XZoneInfo*, count, sync, suppressSync) | VERIFIED-XZIEL concept via package/zone DB |
| Explicit unload by zone index | DB_UnloadXZone(zoneIndex, ...) | VERIFIED-XZIEL |
| Zone state machine | EMPTY/LOADING/LOADED/COMPLETE/FAILED/UNLOADING | VERIFIED-XZIEL |
| Database-ready barrier | Sys_IsDatabaseReady() used before transitions | VERIFIED-XZIEL |
| Finish-load barrier | DB_FinishLoadXFile hook marks fastfile completion | VERIFIED-XZIEL |
| Inter-zone dependencies | XAssetList.dependCount/depends | VERIFIED-XZIEL |
| Asset ownership by zone | XAssetEntry.zoneIndex/inuse | VERIFIED-XZIEL |
| Asset override chain | XAssetEntry.nextOverride | PARTIAL: logical override_of implemented |
| Zone flags/slots | XZoneInfo alloc/free flags + alloc/free slots | PARTIAL: storage modeled; only 0x10000 meaning directly verified |
| 10 XFile memory blocks | TEMP, RUNTIME V/P, DELAY V/P, V/P, STREAMER_RESERVE, STREAMER, MEMMAPPED | VERIFIED-XZIEL model |
| Asset hash/type lookup | DB_FindXAssetHeader / enum / names | PARTIAL: registry lookup implemented, not full T7 hashing/pool semantics |
| Per-type fixed pools | public T7 reversing exposes pool concepts but exact limits vary | MISSING |

## Asset taxonomy

T7 exposes 0x67 normal XAsset types including physics, animation, XModel/XModelMesh,
materials/shaders/images, sound, clip/world/map entities, weapons, FX, AI/character,
raw/script assets, barriers, penetration/damage tables, animation state machines,
behavior trees, cameras, navmesh/navvolume and streamer hints.

XZIEL currently groups content into 24 higher-level package families. That is useful
for package policy but is not enough for T7-level runtime introspection.

Required:
- keep the 24 family layer;
- add a lower-level typed asset registry;
- every artifact must resolve to a concrete runtime asset type;
- each type must declare loader, residency class, dependency edges, destroy path,
  and readiness contribution.

Status: PARTIAL.

## Renderer / world

| Capability | XZIEL status |
|---|---|
| Static geometry scene | VERIFIED-XZIEL |
| Authored transforms/hierarchy | VERIFIED-XZIEL |
| UV0..UV3 | VERIFIED-XZIEL |
| Authored tangents | VERIFIED-XZIEL |
| Base color/material bindings | VERIFIED-XZIEL |
| Normal maps | VERIFIED-XZIEL |
| PBR scalar bindings | VERIFIED-XZIEL |
| Baked lightmaps | VERIFIED-XZIEL |
| Reflection cubemap | VERIFIED-XZIEL |
| Authored local/global lights | VERIFIED-XZIEL |
| Height fog | VERIFIED-XZIEL |
| Full render-world object equivalent to GfxWorld/ComWorld/ClipMap | PARTIAL |
| Dynamic decals / marks / full FX integration | MISSING/PARTIAL |
| Destructibles | MISSING |
| Dynamic world streaming cells tied into Zone DB | PARTIAL |
| Full shader/technique-set registry | PARTIAL |

## Physics / collision / navigation

T7 asset taxonomy contains PhysPreset, PhysConstraints, ClipMap, GameWorld,
NavMesh and NavVolume. Zombies scripts additionally use zone/spawner traversal.

XZIEL:
- collision reference data exists;
- no dedicated XZIEL collision registry/gate found;
- no dedicated navmesh/navvolume loader/gate found.

Status: MISSING as a BO3-style first-class runtime layer.

Required gates:
COLLISION_READY
NAV_READY
PHYSICS_READY

## Animation / actors / AI

T7 exposes XAnimParts, Character, AIType, AnimSelectorTableSet,
AnimMappingTable, AnimStateMachine, BehaviorTree and BehaviorStateMachine.

XZIEL has mobile-animation plans and Vril animation patches, but no central
typed animation/rig/AI registry under engine/xz.

Status: PARTIAL/MISSING.

Required:
RIG_DB_READY
ANIM_DB_READY
AI_ARCHETYPE_READY
BEHAVIOR_DB_READY

## Script VM / game systems

Public BO3 Zombies scripts show a modular system graph using #using/#insert,
REGISTER_SYSTEM and explicit precache directives. Core systems include zone
manager, spawners, weapons, blockers, audio, equipment, perks, powerups,
Mystery Box, player/game logic, AI, client fields and UI.

XZIEL currently executes gameplay largely through the existing Vril/QuakeC
bridge and patch scripts.

Status: PARTIAL. It can express gameplay, but it does not yet expose a BO3-style
script module registry/dependency/precache gate.

Required:
SCRIPT_MODULE_DB_READY
SCRIPT_DEP_GRAPH_READY
PRECACHE_READY
GAME_SYSTEM_REGISTRY_READY

## Weapons / Zombies gameplay database

XZIEL has:
- BO3 weapon specs/runtime bridge;
- weapon catalogs and ID registry;
- Pack-a-Punch catalog;
- Mystery Box pools;
- perk, powerup and GobbleGum reference catalogs.

Status: PARTIAL. Data coverage is strong, but these are not yet universally
registered through the new typed Zone/Asset DB.

Required:
WEAPON_DB_READY
PAP_DB_READY
MYSTERY_BOX_READY
PERK_DB_READY
POWERUP_DB_READY
GOBBLEGUM_DB_READY
SPAWNER_ROUND_READY

## Audio

T7 has dedicated sound asset types and public Zombies scripts initialize audio
as its own system. CoD tooling also distinguishes loaded vs streamed audio.

XZIEL currently has gameplay/audio patching outside engine/xz, but no central
audio alias/bank registry tied into package boot and residency.

Status: MISSING as a first-class BO3-style subsystem.

Required:
SOUND_BANK_READY
SOUND_ALIAS_READY
AUDIO_STREAM_POLICY_READY

## FX

T7 has FX, tag FX, impact FX/sound, player FX, surface FX/sound tables and
explicit script precaches.

XZIEL currently has combat FX patches but no complete typed FX registry.

Status: PARTIAL/MISSING.

Required:
FX_DB_READY
IMPACT_DB_READY
SURFACE_FX_DB_READY

## HUD / UI / client fields

BO3 Zombies scripts use LUI, HUD utilities, menus and clientfields.

XZIEL has mobile HUD/weapon HUD implementation, but no general UI asset/module
registry tied to package boot.

Status: PARTIAL.

Required:
HUD_ASSET_READY
UI_MODULE_READY
CLIENTFIELD_SCHEMA_READY

## Multiplayer / replication

BO3 maintains server/client script instances, game state, clientfields and
network replication independently from rendering.

XZIEL has a multiplayer target and package-family contract but the full 4-player
authoritative replication/voice/runtime schema is not yet represented as a
complete engine/xz subsystem.

Status: MISSING/PARTIAL.

Required:
REPLICATION_SCHEMA_READY
SERVER_AUTH_GAMESTATE_READY
PLAYER_STATE_READY
VOICE_SESSION_READY

## Streaming / residency

T7's XFile block split provides explicit temporary/runtime/delayed/streamed/
memory-mapped storage classes.

XZIEL has stream residency and performance governor infrastructure.

Status: PARTIAL but architecturally aligned.

Required next:
- bind every typed asset to one memory class;
- keep source fidelity unchanged;
- preload metadata/gameplay definitions;
- stream textures/audio/animation/cold geometry without destructive downscale;
- unload in dependency-safe order.

## Final activation barrier

A map must not become MATCH_READY merely because a first frame rendered.

Required final barrier:

PACKAGE_VISIBLE
&& ZONE_DB_READY
&& ALL_ZONE_DEPENDENCIES_COMPLETE
&& WORLD_READY
&& MATERIAL_SHADER_READY
&& COLLISION_READY
&& NAV_READY
&& PHYSICS_READY
&& RIG_DB_READY
&& ANIM_DB_READY
&& AI_BEHAVIOR_READY
&& SCRIPT_MODULE_DB_READY
&& PRECACHE_READY
&& WEAPON_GAMEPLAY_DB_READY
&& AUDIO_READY
&& FX_READY
&& HUD_UI_READY
&& REPLICATION_READY
&& RENDER_FRAME_READY

Only then:
MATCH_READY = 1
ROUND_START_ALLOWED = 1

## Bottom line

XZIEL does NOT yet have every subsystem BO3/T7 has. It now has a much stronger
BO3-style DB/zone/package/render foundation, but collision/nav, animation/AI,
script-module/precache, audio, FX, UI/clientfield and replication registries
must become first-class readiness-gated runtime systems before claiming
functional engine-level parity for complete map loading.
