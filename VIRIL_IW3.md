# VIRIL IW3 — XZIEL NZ:P v0.26 source baseline

This is an isolated experimental branch named **Viril IW3**.

**Purpose:** snapshot the complete and precisely pinned source-code baseline used to
produce the original Android XZIEL/Vril v0.26, before attempting any IW3 integration.
**No IW3 renderer, weapon assets, gameplay changes or engine merge is performed here.**

Base branch:
`recovery/xziel-nzp-v026-official-buttons-20261011`

Verified original v0.26 source pins from `scripts/prepare_android.sh`:
- Vril: `aaa474061bff5d0e3aa471ac01f5f0e01b4fca31`
- QuakeC: `8a77f1ce45f1a2b9aa0afb301446954fda40e696`
- SDL (SDL2 branch): `b90ac95029d801c5abc59472ba8e2200dff31e1e`
- SDL2_mixer: `34370d92840d5aa32b4369dc56c6735ef7adf1a8`
- gl4es: `81547d986798e876de8b434193920b606a72363f`

The original XZIEL v0.26 patch series from `scripts/prepare_android.sh` must
be applied **in its documented order** to those pinned sources, without changing
game behavior. The vendor source import workflow copies these full trees into
`third_party/viril-iw3-v026/` and records their provenance. The original
recovery branch and `main` are not modified.

**Important:** Code is separate from distributable art/game assets. Retain each
upstream license. Do not mistake imported sources for a validated Android APK.
