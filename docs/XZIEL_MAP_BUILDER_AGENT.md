# XZIEL Map Builder Agent v1

This branch adds a repo-native Blender automation loop for Sanctum.

## Design goal

The agent must be able to change a small declarative plan in GitHub, let Blender execute it headlessly, then inspect evidence from the workflow artifact before making another change.

The pipeline is intentionally locked to existing authored assets:

- `geometry_policy` must be `existing-assets-only`.
- `allow_new_architecture` must be `false`.
- The source object must already exist in the upstream .blend.
- The requested Geometry Nodes group must already exist on that object.
- The harness does not create church/cathedral meshes, walls, arches, towers, or decorative architecture.
- Geometry changes are limited to exposed inputs on the existing Geometry Nodes modifier plus object transforms.

## Current source

The workflow pulls:

- IRCSS/Blender-Geometry-Node-French-Houses
- `GeometryNodesFrenchHous.blend`
- object `Catehdral`
- Geometry Nodes group `Generate Cathedral Combined`

The external repository's MIT license is checked before Blender runs.

## Closed loop

1. Edit `tools/sanctum_v2/map_builder_plan.json`.
2. Push triggers `XZIEL Map Builder Agent`.
3. Blender 5.2.2 opens the upstream authored .blend.
4. The harness validates the source and policy.
5. Optional exposed Geometry Nodes inputs are applied by socket name or identifier.
6. The evaluated mesh is measured.
7. Six review cameras render PNG evidence.
8. The evaluated result exports to GLB.
9. `agent-report.json` records source revision, geometry stats, node inputs, render files, and GLB size.
10. The workflow uploads the complete evidence bundle.

This gives a remote/mobile-friendly equivalent of a live Blender agent loop: GitHub is the command channel and Actions is the Blender worker.

## Why this instead of a remote MCP socket

A normal Blender MCP server listens locally, usually on `127.0.0.1`. That is ideal when the model and Blender share one machine, but it does not directly bridge this ChatGPT session to a short-lived GitHub Actions runner.

The JSON-plan workflow solves that deployment mismatch while preserving the important capabilities: deterministic scene edits, screenshots, validation, and exports.

A local Blender MCP server can later be added as a faster interactive front end while keeping this CI harness as the reproducible authority.

## Output artifact

`XZIEL-Map-Builder-Agent` contains:

- six PNG review renders
- `sanctum-cathedral-agent.glb`
- `agent-report.json`
- `agent-report.txt`
- Blender execution log
- pinned upstream source revision

## Next extension points

The plan schema is deliberately small for v1. Future revisions can expose only verified upstream controls, camera presets, material choices from approved libraries, collision/export passes, and XZIEL packaging without weakening the existing-assets-only gate.
