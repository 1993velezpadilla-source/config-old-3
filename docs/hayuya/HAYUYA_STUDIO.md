# HAYUYA Studio

HAYUYA Studio is the touch-safe local/LAN interface for the HAYUYA image-to-3D pipeline.

## What v1 does

- uploads one or many reference images;
- starts a real Hayuya job;
- streams Hayuya stdout events live over Server-Sent Events (SSE);
- shows the current pipeline stage;
- shows candidate meshes as they become available;
- normalizes OBJ/PLY/STL candidates to viewer GLB when possible;
- shows the final champion GLB in an interactive 3D viewer;
- shows candidate/champion information and the live pipeline log;
- works in desktop, tablet and phone layouts;
- serves large GLB files with HTTP byte-range support;
- preserves all actual Hayuya outputs under the job directory.

The UI does not fake neural-network progress percentages. The progress bar is a milestone/stage indicator based on real Hayuya events. A backend that only emits a mesh when inference completes cannot expose intermediate geometry until that backend is instrumented with real checkpoints.

## Windows / Legion Go launch

Double-click:

`tools/hayuya3d/HAYUYA_STUDIO_LAN.bat`

or from a terminal:

```bat
python tools\hayuya3d\studio_server.py --lan --port 8787
```

The terminal prints addresses such as:

```text
HAYUYA_STUDIO_READY
  http://127.0.0.1:8787
  http://192.168.x.x:8787
```

Open the `192.168.x.x:8787` address on a phone or tablet connected to the same trusted Wi-Fi/LAN.

Windows Firewall may ask whether Python is allowed on private networks. LAN access requires allowing the server on the private network.

## Phone workflow

1. Open the LAN URL in Chrome/Safari.
2. Tap the reference box and choose photos from the phone.
3. Select profile / asset mode / portable target.
4. Tap **Generate 3D**.
5. Watch Live Arena and Pipeline.
6. Tap a candidate to inspect it in 3D.
7. When Hayuya chooses the champion, the viewer switches to the final GLB.

The heavy generation still happens on the machine running Hayuya. The phone is a remote control and interactive viewer, so TRELLIS/TripoSG/etc. do not need to run on the phone itself.

## Network model

Studio binds to localhost by default.

Use `--lan` only on a trusted local network. LAN mode binds to `0.0.0.0`, making the Studio port reachable by other devices that can reach the computer.

This v1 does not expose Studio to the public internet and does not include cloud tunneling.

## 3D viewer

Studio pins Google `model-viewer` 4.3.1. The Hayuya host machine downloads and caches that viewer under `.hayuya/studio-vendor/`, then serves it over the same LAN at `/vendor/model-viewer.min.js`. After the host cache exists, the phone does not need its own internet connection to load the 3D viewer.

## Paths

- server: `tools/hayuya3d/studio_server.py`
- UI: `tools/hayuya3d/studio/`
- tests: `tools/hayuya3d/tests/test_studio_server.py`
- jobs: `out/hayuya3d/studio-jobs/<job-id>/`

Each Studio job keeps its uploaded inputs, stdout log, Hayuya output tree, viewer previews and portable outputs together for audit/reopen work.

## Current real-time boundary

Current v1 streams orchestration events in real time:

- planning
- ViewForge
- candidate completion
- refinement
- Mesh Doctor
- retopology
- GamePrep
- Portable Pack
- QA
- final model/champion

The next real-time depth level is backend-specific inference telemetry/checkpoint previews. That must be implemented honestly per backend; Studio will not invent a fake percent while a model is computing internally.
