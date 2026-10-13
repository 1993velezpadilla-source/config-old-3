# Dead Cell: REAL new zombie import contract

**STATE: BLOCKED ON ACTUAL AUTHOR MESH / RETARGETED OUTPUT; no new-zombie APK available.**

## Root cause confirmed 2026-10-13

The released `XZIEL-v026-DeadCell-VRIL-ENGINE-8284-ARM64.apk`
was labeled as an engine stress test. Its build script runs
`tools/vril_hd/build_alias_8284_stress.py` against the original
`nzp/models/ai/zfull.mdl` from NZ:P. It only subdivides the stock
mesh to 8,284 triangles and preserves 211 stock animation frames.
It **never imports** the Hotstrike Studio `SZombie.zip` model.
Raising native Vril geometry ceilings to 16K does not create new art.

The user's Pixel Fold screenshots confirmed recognizable stock zombies.
The user wants the **authentic new zombie**, not a refined NZ:P zombie.

## Required input (do not put source ZIP in this public Git repository)

- Original `SZombie.zip` acquired directly from
  https://hotstrikestudio.itch.io/free-stylized-dark-fantasy-zombie
- FBX / Blend rig and PBR materials from that ZIP (original has
  approximately 8,286 triangles, 2K textures, T-pose with humanoid rig).
- Actual retargeted, animated, Quake MDL v6 replacement `zfull.mdl`
  with real source mesh topology and QuakeC-compatible action frames.
  A stock subdivided `zfull.mdl` is **not** an acceptable substitute.
- UV-mapped `xziel_zombie_hd_0.png` diffuse atlas (1024 or 2048);
  normal/roughness/metalness need explicit GLES renderer support to
  preserve full PBR appearance. A PNG copied into the package alone is
  **not proof** that Vril binds it.

Hotstrike license allows the asset in finished games, including modified
versions; it does not permit redistributing a raw asset pack as standalone
downloads. Keep source archives out of public artifacts and releases.

## Gate order

1. **Source proof:** inspect original author FBX/Blend, UV, armature,
   materials and asset hashes; no stock-only conversion.
2. **Model and renderer integration:** orientation face toward player,
   correct center/scale/pivot, real UV texture bind, animation clip mapping
   for idle/walk/run/attack/hit/death; make sure multiple zombie variants
   and detachable body part models do not silently revert to old geometry.
3. **APK-byte proof:** build Dead Cell ONLY with the original touch HUD,
   developer menu and all weapons; compare final APK's **nested**
   `assets/nzp-data.zip` MDL and PNG bytes with their converted sources.
   Re-open/install the APK if Android caches old extracted data.
4. **Phone proof:** record front/side/back screenshots, walk/run/attack,
   headshots vs torso and die/disappear, performance with several enemies.

## Non-negotiable release policy

`python scripts/guard_hotstrike_real_zombie.py \
  --source-zip /secure/SZombie.zip \
  --stock-mdl /tmp/stock-zfull.mdl \
  --converted-mdl /tmp/hotstrike-animated-zfull.mdl \
  --diffuse-png /tmp/xziel_zombie_hd_0.png \
  --apk /tmp/XZIEL-DeadCell-REAL-Zombie-arm64.apk \
  --report /tmp/real-zombie-provenance.json`

This gate **cannot automatically prove** that the human-shaped mesh or
animations look correct. It rejects the known synthetic 8,284 model,
stock bytes, missing source, T-pose-only conversions, missing render
binding and wrong ZIP payload. CI unit-test GREEN means only that those
guards work. No user-facing 'real zombie' release until on-device proof.
