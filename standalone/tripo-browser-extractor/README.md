# Tripo Browser Extractor (standalone)

Independent experiment. It does **not** import Hayuya code and does not modify Hayuya assets, gates, or workflows.

## What it does

The script runs inside a loaded Tripo Studio model page and serializes the Three.js mesh already present in browser memory into a GLB. It is intended for models you own or otherwise have permission to export.

Compared with the May-2026 proof-of-concept gist, this implementation is rewritten from scratch and adds:

- safer Vue/TresJS scene discovery;
- support for interleaved BufferAttributes through attribute getters;
- correct Uint16/Uint32 glTF index accessor selection;
- world-transform baking so page transforms do not disappear from the export;
- automatic vertical texture correction;
- GLB header/length validation before download;
- key diagnostics: mesh name, vertices, indices, texture state, source mesh count.

## Browser usage

1. Open a model you own in `https://studio.tripo3d.ai/3d-model/<id>`.
2. Wait until the model and texture are fully visible.
3. Open DevTools → Console.
4. Paste the complete contents of `tripo_scene_exporter.js`.
5. The browser should download `tripo_<id>.glb`.

The console prints a `DONE` object with vertex/index counts and file size.

## Current v1 limits

This first runnable version intentionally targets the primary/largest visible mesh, matching the practical behavior of the original proof of concept. A multi-mesh character, multiple material slots, normal/ORM maps, skins, morph targets, and animations need a v2 scene-graph exporter.

No Tripo API credits are required for **exporting geometry that is already loaded in your browser**. This does not generate a new model and does not bypass the generation step.

## Validation

```bash
node --check tripo_scene_exporter.js
```
