# WaW HD Android ARM64 — Independent Native FPS Engineering Demo v0.2

**NOT a playable port of World at War Zombies HD.** This is an independently
written *native* prototype to validate reusable components for a future port:
a perspective OpenGL ES 2.0 3D camera, ARM64 C++ simulation, FPS touch controls,
procedural humanoid enemies, hitscan, reload and endlessly incrementing rounds.

No touchHLE, iOS executables, embedded IPA, DTRZ game assets, emulation,
Marmalade binaries or original protected game resources ship in this APK.
The test level is an original low-poly corridor, **not** Nacht der Untoten.

## Controls (landscape)

- Left bottom translucent circle: virtual movement stick (drag in any direction).
- Right half outside buttons: drag to look around (yaw and pitch, live 3D camera).
- Bottom right **FIRE**: hold to fire, 8-round demo magazine, hitscan ray.
- Right upper **ADS**: hold to zoom field-of-view and reduce look sensitivity.
- Lower mid-right **RLD**: tap to reload (1.55s).
- Left mid **RUN**: hold to sprint. Sprint **does not cancel reload**.
- If health reaches zero, tap screen to restart the test encounter.
- Upper HUD: wave, hit points, kills, ammunition, reload/next-wave state.

## Validated model and tests

- Android thin Java wrapper implements pointer-ID-safe multitouch.
- C++17 `gameplay.h`: deterministic, bounded, allocation-free array-based
  enemy simulation, movement, basic AI pursuit/melee, timed firing and
  3D hitscan ray-to-sphere collision.
- `native_scene.cpp`: GLES2 3D geometry, walls, floor, simple pseudo-zombie
  test dummies, camera, crosshair, primitive bitmap text and touch UI.
- `gameplay_test.cpp` host test checks spawn, raycast kills, reload while
  sprinting, movement bounds, melee damage, game-over and restart.
- Github Actions checks native `arm64-v8a/libwaw_hd_port.so` is an
  AArch64 64-bit ELF and inspects APK for forbidden emulator/iOS payloads.

**Limitations:** no original maps, original models, original weapon models,
animations, textures, audio, real zombie navigation, barricades, power,
Mystery Box, perks, Pack-a-Punch or multiplayer. Enemy geometry is just an
animated rectangular dummy, not the original WaW zombie. Waves increase
without a numerical round cap but on-screen dummies are limited to 64 to
avoid device overload. Gameplay balance does not claim parity with WaW.

## Reproducible build

Run `gradle --no-daemon :app:assembleDebug` in this directory with JDK 17,
Android SDK 35, NDK 27.2.12479018 and CMake 3.22.1. The APK appears at
`app/build/outputs/apk/debug/app-debug.apk`. The authoritative build
result is workflow `waw-ipad-hd-native-arm64-bootstrap.yml`.

**Gate semantics:** CI GREEN means APK built and inspected, not tested on a
Pixel Fold. Device rendering/input require the owner's hands-on check. The
`WAW_IPAD_HD_NATIVE_PORT.md` milestones remain pending until verified on
original game content with the owner's legal rights to use those files.
