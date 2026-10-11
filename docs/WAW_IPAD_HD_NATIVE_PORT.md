# World at War Zombies HD iPad → Android ARM64 (native-only)

**Acceptance criterion:** a self-contained Android APK compiled for AArch64 with an Android-native game loop. No touchHLE, no iOS execution layer, no bundled emulator, no VM, and no binary translation. The game must enter Nacht, render a first-person frame and let a real user fire at moving, damageable zombies on a Pixel Fold before anyone calls the port playable.

## Verified source facts (Phase 1)

- iPad iOS v1.5.0 is a **32-bit ARMv6 Mach-O**, not an Android ELF/AArch64 executable.
- The archive contains a Marmalade/S3E executable with `s3e_code` and `s3e_data` sections and five DTRZ resource archives totaling 45 files. Resource extraction is not source-code recovery.
- The prior iPad resource audit has **Nacht** and **Verrückt**, not the four-map iPhone set. If the project needs the other maps, compare their *separate iPhone assets* and resolve HD compatibility explicitly; never claim they shipped in the iPad HD IPA.
- The iPhone and iPad archives must remain outside the public repository and outside published CI artifacts. A job/artifact name containing “PRIVATE” **does not make an artifact in a public repository private**.
- An earlier workflow also built a touchHLE **compatibility experiment**. Its success does **not** mean the native port exists or that Android gameplay works. That architecture is excluded from the requested deliverable.

## Phase 2 — inspect original code, no emulation

`.github/workflows/waw-ipad-hd-rea-native-audit.yml` analyzes the original iPad ARMv6 Mach-O with REA + Ghidra 12.1.4. It checks the original resource manifest and confirms an actual decompiler analysis attempt. Only hashes, counts, pass/fail and stage metadata may be published. Original IPA, Mach-O bytes, DTRZ files, strings and decompiler output stay on the ephemeral CI runner and are deleted when the job completes.

The REA tool is **not a converter**: it returns program evidence and pseudocode from which engineers may derive independently written behavior for Android. Successful decompilation is only the start of implementation.

## Required native milestones (all must have actual evidence)

1. **S3E and game loop map:** identify startup/exit, time, memory, rendering, audio, touch, archive access, scene transitions and input-to-weapon calls in the original. Record supported function-level evidence without distributing protected code.
2. **Independent ARM64 engine:** C++/Android NDK application with native activity and EGL/OpenGL ES or Vulkan, Android audio and input. Compiles into `libgame.so` for `arm64-v8a`; must have **no emulator dependencies**.
3. **Archive readers + renderer:** load only separately provided, legitimately usable content; correctly reproduce textures, animation poses, map geometry and draw ordering, tested on device.
4. **Full offline gameplay:** Nacht player movement, ADS, shooting, damage, reload, 3D zombie AI/nav/combat, windows/barricades, waves, ammo and death/reset. No arbitrary 20-round cap. Keep sprint and reload independent.
5. **Other systems:** Mystery Box, wall buys, perks, round pacing, doors and HUD; then Verrückt and applicable iPhone-sourced maps with explicit quality/compatibility validation.
6. **Mobile pass:** dual thumbsticks, editable semitransparent touch layout, ADS-only gyro, orientation/landscape, frame time, audio latency, device thermal/memory gates and offline stress testing. Add online 4-player only after offline baseline is stable.
7. **Release:** sign APK, cold boot twice on Pixel Fold, play several full rounds without emulator/runtime bridging; confirm content redistribution rights before any public build.

## Gate labels

- `EXTRACTION_GREEN`: original source package inspected. **Not an APK.**
- `REA_GHIDRA_GREEN`: original code accepted for static analysis. **Not an Android engine.**
- `ARM64_BUILD_GREEN`: original native Android executable built. **Not necessarily playable.**
- `PIXEL_FOLD_GAMEPLAY_GREEN`: real-device, native engine gameplay and combat verified. **First genuinely playable gate.**
- `CONTENT_AND_MAPS_GREEN`: assets/maps/mechanics verified against the actual target sources.

If any gate is unobserved, report it as **pending** rather than inventing progress.
