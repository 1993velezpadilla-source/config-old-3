# VIRIL IW3 - protected copy of XZIEL / Vril v0.26

This experimental branch is independent of the stable **XZIEL v0.26**
recovery branch and `main`. Do not merge or overwrite the stable recovery
branch without the owner's explicit instruction.

## Complete baseline

- Full original Vril, QuakeC, SDL, SDL_mixer and GL4ES source trees:
  `third_party/viril-iw3-v026/`.
- Original v0.26 gameplay, 3D weapon loader, gun positions, ADS, reload,
  original maps, round mechanics and Android touch-control patches retained.
- Original Android launcher, build files, maps tooling, multiplayer support,
  official 12-button PNG skins and source patch scripts retained in this branch.
- Exact original native code pins: Vril
  `aaa474061bff5d0e3aa471ac01f5f0e01b4fca31`; QuakeC
  `8a77f1ce45f1a2b9aa0afb301446954fda40e696`.

## Assets: runtime + original editable 3D source

The full NZ:P game data (weapons, models, frames, maps, audio, textures) is
assembled from the upstream official release by
`scripts/prepare_android.sh`; XZIEL's own touch skins and newly compiled
QuakeC are added before packaging. The data is inside the generated APK.
Separately, the VIRIL IW3 workflow archives the upstream assets repository
with its Blender and other model/map authoring sources.

**Runtime assets and full original 3D authoring assets are not stored as
thousands of new Git blobs inside this branch.** They are packaged separately
with the complete-game APK/source archives via the GitHub Actions workflow
`.github/workflows/viril-iw3-v026-full-game.yml`. When successful, that
workflow uploads CI artifacts and publishes a persistent prerelease backup.

## Protect the existing stable Android installation

Build with `bash scripts/prepare_viril_iw3_android.sh`, then run
`./gradlew :app:assembleDebug` inside `build/android-project`.

- Original stable APK: `com.xziel.nzp`.
- VIRIL IW3 APK: **`com.xziel.viriliw3`**.
- Two Android package IDs mean the VIRIL IW3 APK can be installed alongside
  the original, with separate app-internal storage and saves.
- No original gameplay change or IW3 renderer integration in this baseline.
- A successful package build is not proof of real-device gameplay testing.

Only edit this experimental branch for the next idea. Do not apply
experiments to the stable XZIEL v0.26 release.
