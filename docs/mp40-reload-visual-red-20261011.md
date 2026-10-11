# MP40 reload — real camera evidence, VISUAL RED (2026-10-11)

Source: real Godot 4.6.1 Black Pines `Player/Head/Camera3D` rendered 12 first-person frames with the actual Aether MP40 GLB and T4 marine source hands GLB, in separate render-only branch (no APK). HUD intentionally hidden; no substitute meshes.

GitHub evidence: [twelve real camera renders](https://github.com/1993velezpadilla-source/config-old-3/actions/runs/38153579753). User reports the earlier APK still wrong: gun reloads toward right, not the original left-side behavior.

**IMPORTANT: Previous GREEN was misleading.**
The shipped gate `black_pines_menu_mp40_reload_gate.gd` confirms only source j_clip **local axis**, not the actual rendered hand socket + weapon motion. The new runtime manual-animation probe requires actual camera-space magazine motion and saves frames, but its own CI success means **capture succeeds**, NOT correct handedness. First screen probe was also falsely static because `AnimationPlayer.pause()` cleared `current_animation`; a second probe explicitly plays/seeks/advances the mixers and rejects static j_clip. Never use the first attempt as visual evidence.

## Measurements from correct second probe

- Tactical, actual `gun_root` x in camera: +0.099m at 2%, +0.079m at 18%, **+0.131m at 34%**, +0.121m at 50%, +0.141m at 68%. Whole weapon stays RIGHT. It must not be mistaken for a left-side gun reload merely because the magazine bone moved left.
- Tactical, `j_clip` camera x: +0.103m (2%) to -0.079m (34%); y -0.129m to **-0.497m**, and screen position approximately (798, 1560) at 34% for a 1360x765 viewport. Magazine disappears BELOW screen at critical extraction phase.
- Empty, `j_clip` camera y reaches **-0.671m** at 34%; screen position approximately (932, 1764), far BELOW 765px viewport. Magazine displacement 0.55m is motion, not visible hand-magazine alignment.
- Gun barrel forward stays approximately (x -0.03, y +0.25, z -0.97) at 34%; gun visibly swings UP/RIGHT rather than a source-consistent left-side reload.
- **The 12 actual Godot screenshots show the same wrong direction**, confirming the user's device report. No more static axis-only GREEN accepted.

## Root-cause boundary, not yet source-corrected

MP40 `PSA_viewmodel_mp40_reload_empty` source hands animation drives animated **`tag_weapon`** orientation and the full gun. Prior fix altered only the mount quaternion / local `j_clip` axis; that CANNOT correct the complete camera-space weapon movement through the reload. Runtime screenshots confirm this is a hierarchy / animated socket + authored import-space retargeting problem, not a gun clip length problem.

## Next acceptance (must be RED until human visual approval)

1. Inspect the actual source T4 hand skeleton `tag_view → tag_ads → tag_torso → tag_weapon` rotations across both original reloads in the source coordinate system, including import conversion and GLB animation tracks; do not mirror all weapon meshes, fabricate clip trajectories, or change 27 unrelated weapons.
2. Ensure hand fingers physically grip magazine, withdraw, reinsert and regrip while gun motion cants to intended **LEFT** side; check HIP, ADS, 10 bullets, 0 bullets.
3. Render genuine first-person screenshots at 0%, 18%, 34%, 50%, 68%, 88%; assert magazine and hands are visible in viewport at extraction/reinsertion and that whole gun rotates/tilts toward correct side.
4. Compare actual visual frames to authorized original gameplay reference rather than inferring 1:1 from axis math.
5. Only after RED resolved, build new uniquely labeled APK. This audit branch deliberately does not ship an APK.

Status: **VISUAL RED / SOURCE RETARGETING PENDING**.
