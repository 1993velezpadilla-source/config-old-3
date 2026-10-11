# Actual BO1 recovered native subsystem - Android APK gate

This is an **Android diagnostic host** running the actual C++ routines from the pinned BO1 PC recovery project. It is **NOT a playable Call of Duty game**, and has no scene, zombies, 3D renderer, map assets or emulator.

The GitHub Actions workflow fetches the pinned BO1 C++ code in its ephemeral runner, stages it with Windows-only transitive includes isolated, builds an `arm64-v8a` native shared library with JNI, and packages an Android APK. No Activision game assets or files are included. Original function bodies remain unchanged.

The APK can:
- Run authentic original BO1 orientation and asset color decoding code on Android device.
- Choose a locally owned BO1 `.ff` fastfile using Android file picker, copy it to private app storage and probe its format and up to 128 KiB of uncompressed prefix with the recovered DB_AuthLoad zlib functions. It reports the failure if the retail archive is authenticated, wrong-version or otherwise incompatible.

**A GitHub Actions SUCCESS means it was compiled, not that it was launched and tested on a real phone.**

Next actual engineering gate is authenticated FF handling and original DB_AllocXBlocks / XAsset relocation from x86 pointers to native ARM64. The engine's DirectX 9 graphics, input/audio, network and full gameplay code remain not ported.
