# GTA Chinatown Wars Android 3D Mod Lab

## Project isolation

This is a standalone for-fun modding project. It must not depend on, import,
or modify Nacht/XZIEL/ZOMBIESSSSSSS PORTABLE code, assets, workflows, runtime
profiles, or engine assumptions. Shared repository hosting is organizational
only; CTW work stays inside this branch/path and has its own CI gates.


Experimental, clean-room modding workspace for **GTA: Chinatown Wars Android**.

This project does **not** contain Rockstar game data. Bring a legally obtained APK/game install.

## Target

Primary reverse-engineering target:

- Android ARM64 build 4.4.243 when available
- `assets/game.pak`
- `assets/dxt.bin`
- `lib/arm64-v8a/libGame.so`
- `lib/arm64-v8a/libopenal.so`

## Goals

1. Reproduce the PSP Fusion Fix-style 3D / third-person camera on Android.
2. Add a first-person camera mode.
3. Fix player/body/weapon clipping and render-mask issues exposed by low/first-person cameras.
4. Increase visible world distance without near-camera world pop-in.
5. Treat draw distance as a full pipeline problem: far clip + sector visibility + streaming radius + LOD/culling.

## Public reverse-engineering references

- DK22Pac / CTW-Mobile-Explorer — Android `game.pak` resource format.
- ThirteenAG / WidescreenFixesPack — CTW PPSSPP Fusion Fix camera implementation.
- NaGaa95 / gtactw_nx — ARM64 Android `libGame.so` loading/hooking reference.
- spicybung / BLeeds — Blender tooling for Leeds Engine model/world formats.

These projects remain under their respective licenses.

## Phase gates

### Gate A — APK + PAK inventory
`tools/gtactw/ctw_probe.py`:

- confirms the expected ARM64 game/runtime files;
- parses the 24-byte PAK header;
- reads the split 16-bit resource-offset table exactly as documented by CTW-Mobile-Explorer;
- computes logical resource offsets;
- emits JSON suitable for CI logs.

### Gate B — Android symbol/pattern map
Infrastructure is now in place via `tools/gtactw/elf_probe.py`:

- validates ELF64 little-endian AArch64;
- fingerprints the full binary and `.text`;
- extracts GNU build-id when present;
- enumerates static/dynamic symbols;
- verifies known `GameNative` JNI exports;
- groups camera, streaming, LOD/culling and player-render candidates from symbols and strings.

The real Android addresses are intentionally not guessed. They are populated only after probing the user's own `libGame.so`.

### Gate C — 3D camera
Port the behavior of the PSP camera mod without copying PSP addresses. Android symbols/patterns must be found independently.

### Gate D — full-body / near-clip repair
Locate player visibility masks, model-part culling and near-clip behavior.

### Gate E — extended world distance
Patch/parameterize far clip, sector visibility, streaming radius and LOD thresholds together.

## Usage

Inspect an APK without extracting copyrighted assets:

```bash
python tools/gtactw/ctw_probe.py path/to/GTACW.apk
```

Extract only the required files from **your own APK** into a local work directory:

```bash
python tools/gtactw/ctw_probe.py path/to/GTACW.apk --extract ./local_ctw
```

The local extraction directory must not be committed.

Inventory the complete local PAK without dumping it into Git:

```bash
python tools/gtactw/pak_inventory.py ./local_ctw/assets/game.pak --manifest ./local_ctw/pak_manifest.json
```

Extract only selected resource IDs:

```bash
python tools/gtactw/pak_inventory.py ./local_ctw/assets/game.pak --extract ./local_ctw/resources --ids 12,42,900
```

Fingerprint/map the Android runtime:

```bash
python tools/gtactw/elf_probe.py ./local_ctw/lib/arm64-v8a/libGame.so --out ./local_ctw/libGame_report.json --require-jni
```

Patch goals and required gates are machine-readable in `android_patch_targets.json`.


## Native proxy loader

The Android mod uses a separate native proxy instead of permanently editing the
Rockstar binary:

- the original `libGame.so` becomes `libGame_orig.so`;
- CTW3D builds a new proxy named `libGame.so`;
- every known `GameNative` JNI entry is forwarded to the original library;
- right-stick state is captured for the custom camera;
- right-stick click (Android gamepad code 13) cycles stock / third-person /
  first-person camera state while still forwarding the button to the game;
- internal patches are refused unless the runtime build matches a verified
  profile.

The local APK repacker is:

```bash
python tools/gtactw/apk_modpack.py GTACW.apk \
  --loader-so path/to/libGame.so \
  --out GTACW-3D-unsigned.apk
```

Then use Android build-tools to align and sign the local APK:

```bash
zipalign -P 16 -f 4 GTACW-3D-unsigned.apk GTACW-3D-aligned.apk
apksigner sign --ks YOUR_KEYSTORE --out GTACW-3D.apk GTACW-3D-aligned.apk
apksigner verify --verbose GTACW-3D.apk
```

## Version-safe patch profiles

Generate a template from a real `libGame.so` report:

```bash
python tools/gtactw/profile_template.py \
  ./local_ctw/libGame_report.json \
  --out ./local_ctw/ctw-profile.json
```

The template intentionally leaves all six internal patch targets empty until
they are reverse-engineered and verified:

- `camera_update`
- `projection_setup`
- `world_stream_update`
- `sector_visibility`
- `lod_test`
- `player_render`

Once all six are verified, generate the native table:

```bash
python tools/gtactw/profile_emit_c.py \
  ./local_ctw/ctw-profile.json \
  --out projects/gtactw-android-3d/android-loader/ctw_profiles_generated.h
```

The runtime also compares stable JNI RVAs before accepting a profile, so
offsets from one CTW build are not silently applied to another build.


## World streaming census

After extracting or locating `game.pak`, build a metadata-only census of every
named CTW worldblock:

```bash
python tools/gtactw/world_census.py ./local_ctw/assets/game.pak --out ./local_ctw/world_census.json --require-clean
```

The census reports per-worldblock instance/level density, sector counts,
origins and local level bounds. This is intended to guide coordinated
stream-radius/LOD/far-clip tuning rather than blindly increasing a single
draw-distance constant.


## Pinned Android target verification

Before generating or applying a runtime patch profile, validate the user-owned
APK against the pinned Android target:

```bash
python tools/gtactw/apk_identity.py \
  ./local_ctw/GTA_CTW.apk \
  --reference projects/gtactw-android-3d/reference_build_4.4.243.json \
  --out ./local_ctw/apk_identity.json
```

Then run the full analyzer with the same reference gate:

```bash
python tools/gtactw/analyze_apk.py \
  ./local_ctw/GTA_CTW.apk \
  --reference projects/gtactw-android-3d/reference_build_4.4.243.json \
  --out ./local_ctw/ctw_analysis.json
```

A mismatch in package name, version name, version code, or ARM64 ABI keeps the
reference-build gate red. This prevents applying verified internal RVAs to an
unknown binary build.


## Split APK end-to-end analysis

Google Play installs may arrive as a base APK plus configuration/ABI splits.
Analyze a user-owned APKM/XAPK/APKS, ZIP container, or directory of APK splits
without manually merging them first:

```bash
python tools/gtactw/analyze_apkset.py \
  ./local_ctw/ctw.apkm \
  --reference projects/gtactw-android-3d/reference_build_4.4.243.json \
  --out ./local_ctw/ctw_split_analysis.json \
  --profile-out ./local_ctw/ctw_4.4.243_profile.json
```

The analyzer resolves the asset split and ARM64 native split, fingerprints the
actual `libGame.so`, runs ARM64 xref evidence recovery, generates per-target
candidate rankings, and keeps the six runtime patch RVAs pending until each one
has explicit verification evidence.


## Exact-binary profile verification

A runtime profile is not considered ready merely because its RVAs look
plausible. After each of the six targets is manually verified, record the
target's first 16 bytes in `target_verification[*].code_prefix_hex` and bind
the profile to the exact `libGame.so`:

```bash
python tools/gtactw/profile_verify_binary.py \
  ./local_ctw/lib/arm64-v8a/libGame.so \
  ./local_ctw/ctw_4.4.243_profile.json \
  --out ./local_ctw/profile_binary_verification.json
```

The verifier checks the full library SHA-256, `.text` SHA-256, GNU build-id,
three GameNative JNI RVAs, executable placement of all six targets, and their
16-byte code signatures. The native proxy repeats the byte-signature check at
runtime before accepting the patch target set.


## Streaming pressure model

The world census includes a 2D worldblock-origin pressure estimate for
1x/1.5x/2x/2.5x/3x/4x/5x radii. It reports estimated simultaneously loaded
worldblocks and instance counts, including the worst center. This is a tuning
heuristic, not a claim about the engine's exact streaming-radius formula.


## ADB installed-copy collection

If GTA CTW is installed legitimately on an Android device, the project can
collect the installed base APK and configuration/data splits without root and
run the complete local analyzer in one step:

```bash
python tools/gtactw/adb_collect.py \
  --analyze \
  --reference projects/gtactw-android-3d/reference_build_4.4.243.json \
  --out-dir ./local_ctw/adb_apks \
  --manifest ./local_ctw/adb_manifest.json \
  --analysis-out ./local_ctw/ctw_analysis.json \
  --profile-out ./local_ctw/ctw_4.4.243_profile.json
```

The collector uses `adb shell pm path com.rockstargames.gtactw`, pulls only
the installed APK files to the local ignored workspace, then routes the set
through package/version/ABI/signing-certificate validation, PAK/ELF analysis,
GL PLT-call evidence, ped/model census, world streaming census, and profile
template generation.

If more than one Android device is connected, pass `--serial <adb-serial>`.


## ADB one-pass reverse-engineering capture

With the legitimate Play build installed and USB debugging enabled, one command
can collect the installed APK set, persist only the required runtime files,
validate the pinned build, generate the target-evidence profile, disassemble the
top ARM64 candidates, and attach ABI evidence while leaving every ABI status
`pending`:

```bash
python tools/gtactw/adb_collect.py \
  --analyze \
  --reference projects/gtactw-android-3d/reference_build_4.4.243.json \
  --out-dir ./local_ctw/adb_apks \
  --runtime-out ./local_ctw/runtime \
  --manifest ./local_ctw/adb_manifest.json \
  --analysis-out ./local_ctw/ctw_analysis.json \
  --profile-out ./local_ctw/ctw_profile.json \
  --abi-out ./local_ctw/ctw_abi_evidence.json \
  --abi-profile-out ./local_ctw/ctw_profile_with_abi_evidence.json \
  --status-out ./local_ctw/ctw_profile_status.json
```

The ABI probe uses Android-NDK `llvm-objdump` when available. It demangles C++
symbols, summarizes AArch64 stack/prologue behavior, x0-x7/v0-v7 argument
register hints, calls, branches, and returns. These are evidence only: the
profile deliberately remains `status=pending` until the prototype and adapter
for each hook have been explicitly verified. The optional status output reports
the current gate, verified target/ABI counts, and public 4.4.243 engine-anchor
coverage in the same one-pass run.


## Verified end-to-end build, sign, and optional install

The final playable workflow must use a **profile-specific proxy**, not the
generic CI proxy artifacts. Once the exact 4.4.243 profile has all six target
RVAs, ABIs, trampoline strategies, and native adapters verified, one command
generates both runtime headers, compiles a new ARM64 proxy against those exact
headers, repacks the user's game, signs it, and optionally installs it.

```bash
export CTW_KEYSTORE_PASS='...'
export CTW_KEY_PASS='...'

python tools/gtactw/finish_verified_modpack.py \
  ./local_ctw/GTA_CTW.apk \
  --libgame ./local_ctw/lib/arm64-v8a/libGame.so \
  --profile ./local_ctw/ctw_4.4.243_profile.json \
  --catalog projects/gtactw-android-3d/adapter_catalog.json \
  --loader-source-dir projects/gtactw-android-3d/android-loader \
  --work-dir ./local_ctw/final \
  --config projects/gtactw-android-3d/ctw_modhub.example.ini \
  --keystore ./local_ctw/ctw3d.keystore \
  --alias ctw3d \
  --report ./local_ctw/final/report.json
```

If any verified hook requires advanced ARM64 relocation, also pass a pinned
ShadowHook source checkout with `--shadowhook-dir`. The builder chooses the
minimal or ShadowHook backend from the verified profile and refuses a mismatch.

Add `--install` only when you explicitly want the signed result installed over
ADB. The installer never uninstalls the existing CTW app or deletes its data
automatically. If Android reports a signing-certificate conflict, the process
stops and reports it.

For Play split installs, pass the split directory/APKM/XAPK/APKS source instead
of a monolithic APK. The same verified command repacks all required splits,
signs every output with one certificate, and can use `adb install-multiple`
when `--install` is explicitly requested.

The CI-published minimal/ShadowHook proxies are **template/build-validation
artifacts only** while their generated profile and adapter tables are empty.
They are not the final playable loader for a verified game binary.


## Six-hook verification workflow

The runtime profile stays fail-closed until every target and ABI is explicitly
approved. The intended 4.4.243 workflow is:

1. Run the one-pass ADB collector and emit the enriched profile plus dossier:

```bash
python tools/gtactw/adb_collect.py \
  --reference projects/gtactw-android-3d/reference_build_4.4.243.json \
  --out-dir ./local_ctw/device_capture \
  --analysis-out ./local_ctw/ctw_analysis.json \
  --abi-out ./local_ctw/ctw_abi_evidence.json \
  --abi-profile-out ./local_ctw/ctw_profile_working.json \
  --status-out ./local_ctw/ctw_profile_status.json \
  --dossier-out ./local_ctw/ctw_hook_dossier.json
```

2. After manually reviewing one candidate, explicitly approve its exact RVA.
The helper confirms that the RVA is executable and captures its real 16-byte
code signature from the same `libGame.so`:

```bash
python tools/gtactw/profile_mark_target.py \
  ./local_ctw/lib/arm64-v8a/libGame.so \
  ./local_ctw/ctw_profile_working.json \
  --target projection_setup \
  --rva 0xREVIEWED_RVA \
  --method manual-disassembly \
  --detail "projection matrix path verified from DrawFrame and GL upload" \
  --out ./local_ctw/ctw_profile_working.json
```

3. After the target prototype/calling behavior is manually verified, approve
its ABI and named adapter. The helper requires ABI/prologue evidence for that
same RVA unless `--allow-unprobed` and an explicit trampoline strategy are
supplied:

```bash
python tools/gtactw/profile_mark_abi.py \
  ./local_ctw/ctw_profile_working.json \
  --target projection_setup \
  --prototype "REVIEWED_PROTOTYPE" \
  --adapter ctw_projection_setup_adapter_v1 \
  --method manual-disassembly-runtime-trace \
  --detail "argument/return behavior verified" \
  --out ./local_ctw/ctw_profile_working.json
```

Repeat those two approval steps for:
`camera_update`, `projection_setup`, `world_stream_update`,
`sector_visibility`, `lod_test`, and `player_render`.

4. Verify the completed profile against the exact binary before emitting C:

```bash
python tools/gtactw/profile_verify_binary.py \
  ./local_ctw/lib/arm64-v8a/libGame.so \
  ./local_ctw/ctw_profile_working.json
```

No ranking score, string xref, GL call, ABI hint, or trampoline probe promotes a
target automatically. Approval remains explicit.
