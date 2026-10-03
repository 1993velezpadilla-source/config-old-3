# COD / XZIEL Mobile Audit Port Contract

This document is the canonical bridge between the earlier XZIEL / NZ:P Call-of-Duty-style
mobile audits and the native Godot/Xogot implementation.

## Historical sources recovered from this repository

- `scripts/patch_vril_android.py` — original COD-style native touch controls, HUD positions,
  touch look, ADS behavior, phone gyro and mobile settings.
- `scripts/patch_vril_mobile_v018.py` — per-control scale/opacity, split sensitivity families,
  ADS gyro multipliers and professional CC0 HUD assets.
- `scripts/patch_vril_mobile_v021.py` — dedicated slide control, Track Fire behavior and
  expanded camera sensitivity controls.
- `scripts/patch_vril_mobile_v022.py` — modern movement/HUD/threat pass.
- `scripts/patch_vril_mobile_v024.py` — slide camera presentation pass.
- `scripts/patch_vril_camera_feel.py` — stance eye-height smoothing, landing spring and
  sprint presentation.
- `scripts/build_xziel_icons.py` — canonical XZIEL HUD surfaces + pinned CC0 action glyphs.
- `docs/WAW_ZOMBIES_HORROR_DNA.md`, `docs/ZOMBIES_MAP_DNA_ATLAS.md` — Zombies feel/map DNA.

Relevant historical commits include:
`6f5e723`, `0e2d0ed`, `f383085`, `0614887`, `288f57d`, `cded8bb`,
`174116a`, `d0e196d`, `fa57714`.

## Native first-person scale contract

Godot/Xogot now uses one human-scale authority:

- standing player capsule height: **1.76 m**
- standing capsule radius: **0.36 m**
- standing eye height: **1.60 m**
- crouched capsule height: **1.16 m**
- crouched eye height: **1.03 m**
- base vertical FOV: **66°**
- ADS vertical FOV: **52°**
- sprint vertical FOV: **69°**
- slide vertical FOV: **70.5°**

The 66° vertical FOV is approximately 96° horizontal on a 16:9 display and preserves the
close, readable Zombies scale without the exaggerated wide-angle/toy effect.

Camera presentation recovered from the earlier Vril audit:
- stance eye-height response: **18 Hz**
- landing spring: **17 Hz**
- fast slide camera entry: first **0.14** of slide phase
- slide hold to phase **0.72**, then smooth recovery
- slide camera roll: approximately **1.15°**
- camera/weapon presentation does not alter authoritative hitscan direction.

## Aim / touch / gyro contract

- normal touch look = 1.00 native multiplier
- ADS touch multiplier = **0.62**
- Track Fire: FIRE and ADS+FIRE drags rotate camera while firing
- gyro ADS multiplier = **0.65**
- historical sniper sensitivity/gyro references remain **0.42** for when scoped weapons land
- ADS defaults to Hold; Toggle remains an explicit configurable mode

## Canonical mobile HUD layout

Normalized coordinates recovered from the original mobile implementation:

| Control | X | Y | Radius (screen-height fraction) |
| --- | ---: | ---: | ---: |
| Joystick | 0.170 | 0.740 | 0.120 capture / 0.095 visual |
| FIRE | 0.885 | 0.585 | 0.073 |
| ADS+FIRE | 0.795 | 0.435 | 0.056 |
| ADS | 0.695 | 0.575 | 0.047 |
| Reload | 0.805 | 0.785 | 0.044 |
| Use / Interact | 0.605 | 0.675 | 0.050 |
| Jump | 0.695 | 0.790 | 0.044 |
| Slide / Crouch | 0.745 | 0.825 | 0.044 |
| Knife | 0.915 | 0.800 | 0.044 |
| Pause | 0.965 | 0.075 | 0.036 |
| Grenade | 0.835 | 0.300 | 0.041 |

Native implementation authority: `xogot/scripts/mobile_layout.gd`.

## Official XZIEL HUD skin pack

Native Xogot copy: `xogot/assets/hud/official/`.

The pack contains the original XZIEL procedural surfaces:
- joystick ring / inactive knob / active knob
- small idle / pressed surfaces
- dedicated FIRE idle / pressed
- dedicated ADS idle / pressed
- dedicated ADS+FIRE idle / pressed
- FIRE / ADS / ADS+FIRE glyphs

Action glyphs are pinned from Nieobie/Game-Icon-Pack revision
`b1a5fec8b68c99e7b46484db707610ab2414ad4c`, CC0 1.0:
reload, use, jump, slide, knife, grenade, pause and sprint.

Default visual opacity from the old audit:
- joystick: **0.78**
- touch buttons: **0.82**

## Monja Básica enemy scale contract

Canonical asset: `xogot/assets/zombies/monja_basica.glb`.

- visual height: **1.76 m**
- maximum visual width: **0.74 m**
- maximum visual depth: **0.58 m**
- collision radius: **0.29 m**
- collision height: **1.72 m**
- headshot threshold begins at **84%** of model height

This keeps the common church zombie on the same human-scale reference as the player eye/body,
instead of compensating for map scale by making the enemy artificially large.

## CI gates

The native build must prove:
- `XZOGOT_COD_VIEW_READY`
- `XZOGOT_COD_VIEW_PROBE_GREEN`
- `XZOGOT_OFFICIAL_SKINS_READY`
- `XZOGOT_ENEMY_SCALE_PROBE_GREEN`

These are in addition to the existing movement, weapon, interaction, window traversal,
headshot, round, human-scale church and balcony traversal gates.
