# Zombie Touch HUD v1

Approved Android touchscreen skin pack for NZPortable/NZ:P and XZIEL.

## Exact button identification

| Asset | Function |
| --- | --- |
| `ads_fire_hybrid` | Hybrid ADS + Fire |
| `ads` | ADS / aim |
| `fire` | Hip fire / fire |
| `reload` | Reload |
| `squad` | Squad / team panel |
| `crouch` | Crouch / squat ("eñangotado") |
| `slide` | Tactical slide |
| `prone` | Prone |
| `jump_vault` | Jump / vault |
| `sprint` | Sprint |
| `dolphin_dive` | Dolphin dive |
| `melee_knife` | Melee / knife |
| `grenade` | Grenade / throwable |
| `interact_zombie_hand` | Use / interact |
| `weapon_swap` | Quick weapon swap |
| `weapon_primary` | Primary weapon slot |
| `weapon_secondary` | Secondary weapon slot |

## Android preparation

The runtime PNGs use transparent outer canvases and a low-alpha neutral smoky
center so gameplay remains visible below the controls. The black zombie-hand
silhouettes, icon artwork and metal rim retain stronger alpha. Touch hitboxes
must stay independent of visual alpha and should be about 1.15x the visible art.

- standard action buttons: 256x256 PNG
- hybrid ADS+Fire: 512x512 PNG
- weapon slots: 512x256 PNG

## NZPortable / Vril

Canonical art belongs under `assets/mobile/zombie_touch_hud_v1/png/`.
The Android build copies the approved runtime aliases into `nzp/gfx/xziel/`
without changing touch hitboxes. Existing live mappings are ADS+FIRE, ADS, FIRE,
RLD, USE, NADE, JUMP, SLIDE and KNIFE.

The current combined mobile crouch/slide gameplay behavior remains untouched.
Separate art for CROUCH, PRONE, DOLPHIN DIVE, SQUAD and SPRINT is kept distinct
so those controls can receive independent roles instead of being folded together.

## XZIEL

The same `png/` folder plus `manifest.json` is engine-neutral. XZIEL should bind
the `xziel_action` values directly and draw each texture as one full touch
surface. Pressed state can use a slight scale/tint/opacity change without
changing source art.

## Provenance

This is the user-approved project-generated design. It is not extracted
Call of Duty/Nazi Zombies UI art. Do not mark it as CC0.
