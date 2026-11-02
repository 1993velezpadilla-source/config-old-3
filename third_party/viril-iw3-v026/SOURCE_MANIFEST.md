# Viril IW3 — complete v0.26 source snapshot (not an IW3 integration)

Exact pins from the working original XZIEL NZ:P Android v0.26 recovery:
- Vril: nzp-team/vril-engine @ aaa474061bff5d0e3aa471ac01f5f0e01b4fca31
- QuakeC: nzp-team/quakec @ 8a77f1ce45f1a2b9aa0afb301446954fda40e696
- SDL/SDL2: libsdl-org/SDL @ b90ac95029d801c5abc59472ba8e2200dff31e1e
- SDL2_mixer: libsdl-org/SDL_mixer @ 34370d92840d5aa32b4369dc56c6735ef7adf1a8
- GL4ES: ptitSeb/gl4es @ 81547d986798e876de8b434193920b606a72363f

Each tree contains the **full files** of the pinned upstream revision, plus
the original XZIEL v0.26 source-altering patch sequence as applied by
`scripts/prepare_android.sh`. Original upstream license files are retained.
`.git` object directories are deliberately not duplicated.

No IW3 code was added here; this commit is a stable backup/source baseline.
Art, maps, extracted commercial-game data, and APK output are not included.
