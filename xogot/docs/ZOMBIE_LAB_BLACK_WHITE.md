# ZOMBIE LAB — First isolated playable Godot 4.6 stage (2026-10-13)

**Scope:** an isolated test scene (`res://zombie_lab.tscn`) using the ACTUAL Black Pines player, touch HUD, MP40 weapon code, round director, map physics, zombie AI, hit-zone logic, and a selectable model. The canonical `project.godot`, `main.tscn`, `black_pines.tscn`, Nacht, Church, NZ:P and APEX are NOT edited.

## How to run

Open `xogot/project.godot` in Godot 4.6.1 or Xogot, import assets, then use **Run Current Scene** on `xogot/zombie_lab.tscn`. The project main scene remains unchanged, so use Current Scene rather than Play Project. Touch-friendly overlay at top left:

- **BLACK & WHITE (RAW)** — the actual 20.3 MB `monja_black_white.glb` from the Tripo source; stationary preview only, since the recorded source manifest correctly reports **skins=0, animations=0**.
- **MONJA CLEAN (ANIMATED)** — prior `monja_basica_clean_rig.gltf`, with existing animation clips, to prove our existing AI and animation bridge, *not* to misrepresent this as a rigged Black & White.
- **WAW ZOMBIE (REFERENCE)** — original import (for internal source comparison); should animate in the existing chase/attack/death controller.
- Rotate 180° for authored forward-axis diagnosis, pause/resume chase for rigged models, and re-equip the actual catalog MP40 for firearm/headshot tests.

The map is loaded with **rounds disabled**: one deliberate specimen at a time. Existing Black Pines purchases, windows, perks, HUD, motion, audio, networking, source weapon contracts and geometry remain unchanged. Missing models now fail visibly: the lab **must not** substitute an unrelated zombie mesh and still report success.

## Important findings and blockers

1. Raw Black & White source: `xogot/assets/zombies/monja_elite/source/monja_black_white.glb`. The source folder previously had `.gdignore`, so Godot could not import it; this lab branch removes only that import block, leaving the GLB itself untouched.
2. Captured-human zombie clips already exist under `xogot/assets/zombie_mocap/raw/` (walk, attack, getup, crawl, death). **Existing motion capture is not a rigging solution by itself.** The Black & White mesh still requires a Blender skeleton, weights, mocap retarget, foot contact/turning and export as a NEW versioned runtime GLB with AnimationPlayer. No 0-bone mesh will be advertised as animated.
3. Separately stored `monja_clean/clean_runtime/monja_basica_clean_rig.gltf` already has an authored rig, but belongs to another model. It is a test reference, not a clean conversion of the Black & White asset.
4. Preserve the original 28-weapon catalog; inspect MP40 model orientation, hands/grip anchors, animation frame timing, reload-magazine left side and ADS alignment in the lab later. A catalog `equip_weapon("mp40")` returning true is not yet a visual proof of the reload or hand positions.
5. A static source manifest and runtime headless Godot probe are part of this branch. A green CI result only proves the gates coded here; physical phone rendering and actual user touch validation require a phone APK built *after* import/runtime passes.
6. This lab intentionally includes licensed upstream references for internal experiments. Before any public distribution, verify licenses and substitute original/cleared assets where necessary.

## Stage gates

- **G1:** imported raw Black & White must show her authentic mesh, 0 animations, and allow 180-degree yaw test without replacing her with WaW — `xogot/ci/zombie_lab_probe.gd`.
- **G2:** existing clean Monja rig plays idle/walk/attack/death through existing AI, with genuine AnimationPlayer — same probe.
- **G3:** original WaW reference/MP40 imported and equip works; chest vs head hitbox classification — same probe.
- **G4 (not implemented):** Blender retarget Black & White with weight/cloth/skinning fidelity; correct skeleton, source mocap and real animation clips; headshot geometry and correct forward axis visually confirmed.
- **G5 (not implemented):** Android APK physical test of reload/ADS/fire, audio, collision, navigation/attacks, performance and texture quality.

**Do not promote a model into production before visual+functional phone acceptance.**

### CI

GitHub Actions: `.github/workflows/zombie-lab-blackwhite-gate.yml`. This workflow imports the actual large Godot project with the official free Godot engine on Linux and runs `res://ci/zombie_lab_probe.gd`. It saves raw logs as a workflow artifact. The workflow does not silently convert any red into green and does not claim APK or physical validation.
