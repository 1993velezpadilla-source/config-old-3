# World at War Zombies HD — ARM64 native renderer bootstrap

**This is an independently written Android technical prototype, NOT the original game and NOT a playable port.** It does not embed iOS IPAs, binary translation, touchHLE or original copyrighted assets. It demonstrates a clean ARM64 `libwaw_hd_port.so` rendering procedurally via OpenGL ES 2.0 and receiving touch input from Android.

It is intentionally visually distinct: a procedural corridor, aim marker, crosshair and touch feedback. It contains **zero zombies, maps, original weapons, audio or game mechanics**. Packaging this APK is only `ARM64_BOOTSTRAP_GREEN`, not `PIXEL_FOLD_GAMEPLAY_GREEN`.

To build: `gradle :app:assembleDebug` from this directory with Java 17, Android SDK 35, NDK 27.2.12479018 and CMake 3.22.1. The artifact's APK path is `app/build/outputs/apk/debug/app-debug.apk`. Android physical device validation has not occurred until a user installs it and reports real behavior.

Native-only design: Java is only a thin Android Activity/EGL/touch bridge; game-side rendering is compiled C++17 for arm64-v8a. No emulation and no network permission.
