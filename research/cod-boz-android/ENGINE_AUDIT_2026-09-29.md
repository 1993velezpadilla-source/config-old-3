# Call of Duty: Black Ops Zombies (Android) — Engine Audit

Date: 2026-09-29
Scope: public technical research only. No commercial APK/OBB/DZ/native game binaries are mirrored here.

## Executive finding

The Android BOZ release is not primarily a Java/Kotlin game. The Android layer is a platform wrapper around a native Marmalade/S3E game payload. The important executable boundary is `boz.s3e`, an ARM32 S3E image containing code, an embedded configuration block, a symbol/import table, relocation metadata and an entrypoint. The host/runtime supplies the Marmalade APIs that this payload imports.

For XZIEL, the valuable lesson is the architecture split:

Android/platform shell
-> S3E runtime compatibility layer
-> relocated game image (`boz.s3e`)
-> renderer/input/audio/files/network services
-> game data/resource archives (`.dz`)

This is much closer to a portable game-runtime ABI than to a monolithic Android APK.

## Verified public upstreams

1. https://github.com/12brendon34/COD-BOZ-Partially-Decompiled
   - Original public partial Android decompilation/reconstruction.
   - Confirms Marmalade and package data under `com.activision.boz`.
   - Documents texture/resource packs including `blackops_gles1.dz`, `blackops_dxt.dz`, `blackops_atitc.dz`, and `blackops_etc.dz`.

2. https://github.com/eugene373/COD-BOZ-Partially-Decompiled
   - Modern Kotlin reconstruction of the Android-side layer.
   - Preserves JVM signatures/ABI required by the native side.
   - Explicitly states that this is not yet a complete source-level recreation of the whole game.

3. https://github.com/Producdevity/cod-boz-port
   - MIT-licensed ARMHF S3E loader/runtime recreation.
   - Contains loader/runtime source only and does not redistribute the commercial game data.
   - Best public source for understanding the native boundary.

## Target build identified

Public PortMaster work targets Android BOZ 1.0.11 and documents SHA-256:

`359ee68b6e0a3a66e921ec9b955b290dedb93135fd3c20904bc1bb6f47b5499d`

Use that only as an identity check for a legally obtained copy.

## Native image / S3E container

The open loader identifies the uncompressed S3E magic as `0x55334558` and parses this header-level structure:

- ident
- version
- flags
- arch
- fixup offset/size
- code offset/file-size/memory-size
- signature offset/size
- entry offset
- config offset/size
- original base address
- extra offset/size
- extended-header fields

The loader then:

1. Loads the full S3E image.
2. Parses an import/symbol table from the fixup region.
3. Maps executable memory at the image's expected base.
4. Copies code and zero-fills the remaining code-memory range.
5. Applies internal relocations.
6. Resolves external imports against host-provided Marmalade-compatible functions.
7. Calls the image entrypoint.

Important implication: the game payload is native ARM32 code. Replacing only the Java/Kotlin wrapper does not make the original game payload ARM64.

## Host API boundary

The public runtime reconstructs a broad S3E host surface. Major subsystems observed:

### Memory
- `s3eMallocBase`
- `s3eReallocBase`
- `s3eFreeBase`
- heap compatibility/state

### File system
- open/close/read/write/seek/tell/size
- existence checks
- directories, rename/delete
- memory-backed files
- directory listing

### Runtime/device
- yield/event pumping
- timer dispatch
- quit/pause queries
- device identity strings
- surface dimensions
- debug stubs

### Input
- `s3ePointer*` touch/pointer interface
- keyboard/game-key compatibility
- SDL2 controller discovery
- analog axes, triggers, buttons and hat/D-pad support
- Xperia Play identity emulation is used by the compatibility layer to select a suitable binding set

### Graphics
- EGL host boundary
- OpenGL / OpenGL ES symbol forwarding
- fixed-function-era calls plus framebuffer/shader-era calls
- viewport/scissor translation
- framebuffer tracking
- swap-buffer hook
- frame pacing
- 640x480 reference surface behavior with letterboxing/scaling compatibility

### Audio
- `s3eAudio` and `s3eSound` compatibility
- SDL2 / SDL_mixer backend in the public loader
- 24 sound channels + 2 streamed-audio channels in the recreated host
- PCM conversion/mixing
- callback pumping
- optional capture/render path for voice-style audio

### Networking
- `s3eSocket` compatibility over POSIX sockets
- nonblocking sockets
- TCP/UDP
- async connect/read/write callbacks
- asynchronous DNS lookup
- socket polling
- mDNS/zeroconf for local discovery

### Configuration
The embedded S3E config is parsed by section/key and conditional platform/device rules. The public loader exposes settings for graphics memory/cache, gameplay runtime flags, resource style, online mode, voice state and device identity.

## Resource packs

The public work identifies these BOZ data packs:

- `blackops_etc.dz`
- `blackops_atitc.dz`
- `blackops_dxt.dz`
- `blackops_gles1.dz`

The compatibility layer selects a resource style according to which archive is present. This strongly suggests the same logical game content was packaged in device/GPU texture variants rather than as four independent games.

The public APK extractor also shows that the APK is a ZIP container with Marmalade payload/assets inside, while larger game resources live in the DZ data path.

## Main loop / scheduling

The reconstructed runtime repeatedly pumps:

- input
- audio
- zeroconf
- sockets
- timers

`s3eDeviceYield` acts as an important cooperative scheduling boundary. That is a useful design lesson for XZIEL: platform services can be kept behind one predictable pump rather than spread randomly through gameplay code.

## Rendering observations useful to XZIEL

The public loader wraps EGL/OpenGL calls instead of rewriting the original renderer. It also performs:

- letterbox-aware viewport/scissor adjustment
- default framebuffer tracking
- frame pacing around swap
- presentation overlays
- frame interpolation hooks into the loaded game image

The frame interpolation implementation validates hard-coded signatures/offsets in the known BOZ 1.0.11 image before installing hooks. This shows the original game keeps a transform set and a director/update/interpolate path that can be intercepted without replacing all gameplay logic.

For XZIEL, copy the concept, not the proprietary offsets:
- fixed simulation step
- captured previous transforms
- render-time interpolation factor
- presentation decoupled from simulation

## Audio observations useful to XZIEL

The recreated host distinguishes short sound channels from streamed audio and pumps callbacks from the runtime loop. This is compatible with XZIEL's needs for:
- weapon SFX
- zombie voices
- ambient loops
- UI/music streams
- proximity/voice as a separate capture/render path

Do not copy BOZ assets; copy the scheduling/interface pattern.

## Networking observations useful to XZIEL

The game expects an async socket API and local discovery primitives rather than direct blocking networking calls inside gameplay.

That suggests a clean XZIEL split:
- transport/socket service
- async callbacks/events
- LAN discovery
- matchmaking/server layer above transport
- gameplay replication above that

The public community port also demonstrates that the online endpoint can be abstracted at the host/config boundary, which is architecturally useful even when XZIEL uses its own protocol and servers.

## 32-bit / 64-bit conclusion

The original game payload is fundamentally AArch32/ARM32. A modern Kotlin wrapper can compile for current Android while still depending on 32-bit native game code.

Therefore true modern support has three broad architectural paths:

1. keep a 32-bit process/device compatibility environment;
2. run the 32-bit payload through a translation/compatibility layer;
3. clean-room reimplement/recompile the game logic for ARM64.

For XZIEL, path 3 is the long-term native-engine direction. The S3E loader is still extremely valuable as documentation of the original runtime contract.

## What this tells us about the actual BOZ engine

The engine boundary is approximately:

```
Android app / Kotlin-Java shell
        |
        v
Marmalade S3E platform ABI
        |
        +-- memory/files/config/device
        +-- pointer/controller input
        +-- EGL/OpenGL renderer bridge
        +-- audio/sound callbacks
        +-- sockets/DNS/zeroconf
        +-- timers/yield
        |
        v
ARM32 boz.s3e game payload
        |
        +-- gameplay
        +-- round systems
        +-- player/zombie logic
        +-- UI/frontend
        +-- resource manager
        +-- renderer-side game state
        +-- multiplayer game protocol
        |
        v
DZ resource archives / assets
```

The Kotlin project alone is not the whole engine. The public loader/runtime is currently the clearest map of the native contract.

## XZIEL extraction checklist

Safe research targets to reproduce as our own code:

- S3E-style service table / platform ABI concept
- explicit executable/game-module boundary
- deterministic fixed-step + render interpolation
- centralized pump for platform async services
- resource archive abstraction by hardware format
- device capability/config layer
- touch + controller input normalization
- audio channel/stream separation
- async socket + local discovery abstraction
- renderer compatibility wrapper concept

Do not import proprietary game code, textures, sounds, maps, models, scripts, APKs, OBBs, DZ archives or native libraries into this repository.

## Next audit layers

1. Enumerate every imported symbol used by the BOZ S3E image.
2. Classify imports by subsystem and identify which are actually exercised during boot/gameplay.
3. Map DZ archive structure and resource naming from public tooling/documentation without redistributing data.
4. Trace renderer state transitions and material/texture flow.
5. Trace input -> binding -> player command path.
6. Trace round/zombie/game-state boundaries where public reverse-engineering material permits.
7. Trace LAN/online protocol boundaries at the host interface.
8. Convert the reusable ideas into XZIEL-native interfaces instead of embedding BOZ binaries.

## Source snapshot used

Public loader source inspected at commit-visible URLs around:
`3b444d6003a78f08694e965509477d13a742ebf1`

Key files:
- `src/main.c`
- `src/s3e_image.c`
- `src/s3e_gl.c`
- `src/s3e_runtime.c`
- `src/s3e_input.c`
- `src/s3e_audio.c`
- `src/s3e_socket.c`
- `src/s3e_config.c`
- `src/codboz_assets.c`
- `src/codboz_frame_interpolation.c`
- `tools/apk_extract/codboz_apk_extract.c`


## Host symbol inventory size

From the current public `Producdevity/cod-boz-port` resolver:

- 157 explicit S3E host symbols
- 39 explicit wrapped GL/EGL symbols
- 196 explicit compatibility entries total
- additional `gl*` / `egl*` names may be dynamically resolved by the backend when requested

This gives us a concrete compatibility-surface checklist for XZIEL rather than a vague “Marmalade-like” target.

Primary host groups observed in the explicit table:
- allocation/memory
- file system
- compression
- timers
- device/runtime/debug
- keyboard
- pointer/touch
- accelerometer
- video stubs
- audio/stream audio
- sound channels
- inet helpers
- sockets
- software surface
- GL bridge
- config
- extension hashing

The wrapped GL/EGL list includes state/setup calls such as viewport, scissor, framebuffer binding, fixed-function transforms/material/light/fog calls, selected uniforms, read/copy pixel paths, `eglGetProcAddress`, and `eglSwapBuffers`.

This strongly supports the interpretation that the original BOZ renderer was written across the OpenGL ES fixed-function-to-GLES2 transition era and relied on the Marmalade runtime to smooth platform differences.


## S3E extension layer

The public compatibility runtime shows that BOZ does not rely only on a flat base API. It also queries extension interfaces through `s3eExtGetHash`. Reconstructed extension tables currently include:

- AudioUnit-style capture/render audio interface
- device/platform resource interface
- Xperia Play touchpad interface
- ZeroConf/mDNS discovery interface

This is architecturally important for XZIEL. A clean equivalent would keep a small stable platform ABI and expose optional capabilities through versioned service tables instead of coupling gameplay directly to Android APIs.

Suggested XZIEL analogue:

```
XZPlatformCore
  -> MemoryService
  -> FileService
  -> ClockService
  -> InputService
  -> RenderSurfaceService
  -> AudioService
  -> NetworkService

XZPlatformExtensions
  -> Touchpad/Gyro
  -> VoiceCapture
  -> LANDiscovery
  -> DeviceResources
  -> future platform-specific services
```

The design principle is reusable; the proprietary BOZ implementation/data is not.


## Android shell confirmation and ARM64 clarification

Inspection of the public partial-decomp Android project confirms that the Java entrypoint is extremely thin:

- `com.activision.boz.Main` only extends `IsDeviceActivity`.
- `IsDeviceActivity` extends Marmalade's `LoaderActivity`.
- Device-specific Java handles lifecycle, fullscreen/cutout behavior, storage paths, display metrics and callbacks.
- The manifest declares Marmalade's `VFSProvider` and the expected Android/network/audio permissions.

The project tree contains both an `armeabi-v7a/libs3e_android.so` and an `arm64-v8a/libs3e_android.so`, but this must not be interpreted as proof that BOZ game code itself has been ported to ARM64.

The project's own Gradle configuration currently filters builds to `armeabi-v7a`; the `arm64-v8a` ABI line is commented out. The native `boz.s3e` payload remains the key game executable boundary.

Conclusion:
- an ARM64 Marmalade/runtime library can exist independently;
- the Java shell can be modernized independently;
- neither one converts the original ARM32 BOZ payload into ARM64 game code.

For XZIEL this reinforces the clean-room direction: keep Android platform integration thin and make the actual game/runtime modules native to our own ARM64/Vulkan architecture rather than depending on BOZ binaries.


## Resource pipeline: Marmalade Derbh/DZip and IwResGroup

Public Marmalade tooling confirms that the BOZ `.dz` family uses the Marmalade **Derbh/DZip** archive format.

### Derbh / .dz container

Verified high-level structure:

```
0x00  "DTRZ"
0x04  u16 file_count
0x06  u16 folder_count (includes root)
0x08  root-folder placeholder
      NUL-terminated file names
      NUL-terminated folder paths
      file attribute records
      location-table metadata
      per-file location records
      compressed/stored file payloads
```

Each file has a folder index plus a location record containing an offset, size fields and a compression-method tag.

Known compression methods in public tooling include:
- `0x100` stored
- `0x200` LZMA-alone
- `0x008` gzip/DEFLATE-style data
- additional method values are recognized by readers and may use fallback detection

This means a DZ is not itself a monolithic opaque asset. It is an indexed virtual filesystem/archive layer.

### IwResGroup / .group.bin

Inside extracted DZ files, Marmalade uses serialised **IwResGroup** bundles. A group begins with magic `0x3d` and contains hash-addressed sections.

The important `ResGroupResources` section groups resources by **class hash**, count and per-resource metadata/body.

Public decoders currently recognize classes such as:

- `CIwTexture`
- `CIwMaterial`
- `CIwModel`
- `CIwGxFont`
- `CIwResGroup`
- `CIwResList`
- `CIwResTemplate`

Resource names and classes use Marmalade's 32-bit `IwHashString` system.

### Asset hierarchy

The practical pipeline is therefore:

```
blackops_*.dz
  -> Derbh/DTRZ archive entries
      -> *.group.bin / loose data
          -> IwResGroup
              -> class buckets
                  -> CIwTexture
                  -> CIwMaterial
                  -> CIwModel
                  -> CIwGxFont
                  -> other hashed resource classes
```

This is the first concrete map of BOZ's resource-manager layers.

### Geometry and materials

Public Marmalade parsers show that `CIwModel` is block-based. Known geometry blocks include:

- `CIwModelBlockVerts`: signed 16-bit XYZ vertices
- `CIwModelBlockGLUVs`: signed 16-bit UVs with fixed-point scale 4096
- `CIwModelBlockGLTriList`: unsigned 16-bit triangle indices

`CIwMaterial` stores:
- flags
- multiple RGBA colour channels
- references to textures by hash

Therefore the material->texture relationship can be reconstructed from hashes rather than relying on filenames alone.

### Textures

`CIwTexture` bodies contain dimensions/pitch plus raw texel data. Public tooling supports layouts including:
- RGBA8888
- RGB888
- RGB565
- single-channel/greyscale

BOZ's multiple `blackops_gles1/dxt/atitc/etc.dz` variants should therefore be treated as hardware/texture packaging variants layered above the same logical resource system.

### XZIEL implication

The reusable pattern is:

```
XZArchive
  -> indexed files
XZResourceGroup
  -> hashed resource classes
XZModel / XZMaterial / XZTexture / XZFont
  -> native Vulkan-ready runtime objects
```

We should not copy BOZ game assets, but this architecture gives XZIEL a strong reference for a compact mobile resource pipeline.

## Public tooling references added to audit

- `knot126/Marmalade-Modding`: S3E/DZ/group reverse-engineering utilities.
- `Tatsh/dade`: current open Marmalade decoders for Derbh, IwResGroup, CIwTexture, CIwMaterial and CIwModel.
