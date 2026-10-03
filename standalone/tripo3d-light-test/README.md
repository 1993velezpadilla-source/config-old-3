# Tripo3D Light — standalone probe

This folder is intentionally independent from Hayuya. It imports no Hayuya code and writes no Hayuya assets.

It reproduces the useful idea from `Dragoy/triposr_light` (submit an image-to-3D task, poll it, download the result) but updates the request shape to the current Tripo3D v2 OpenAPI. The old project sends inline base64 image data; the current public docs describe `file.url`, `file_token`, or STS `object` inputs instead.

## Modes

```bash
pip install -r requirements.txt

# Free/offline payload validation
python tripo_probe.py --dry-run \
  --image-url https://raw.githubusercontent.com/VAST-AI-Research/TripoSR/main/examples/chair.png

# Auth/balance smoke test (does not submit a 3D generation task)
TRIPO_API_KEY=tsk_... python tripo_probe.py --auth-check

# Real generation (can consume Tripo credits)
TRIPO_API_KEY=tsk_... python tripo_probe.py --generate \
  --image-url https://example.com/source.png \
  --model-version v2.5-20250123 \
  --out-dir output
```

## GitHub Actions

`Tripo3D Light Standalone` always runs the free validation on pull requests touching this project. A manual run can select `validate`, `auth`, or `generate`. Real generation is **manual-only** so a commit cannot burn API credits accidentally.

For `auth`/`generate`, configure a repository secret named `TRIPO_API_KEY`. Generated GLB/preview files are uploaded as workflow artifacts.

## Isolation contract

- No imports from `hayuya/`, `tools/hayuya3d/`, or Hayuya workflows.
- No writes to Hayuya model folders.
- No Hayuya gates/thresholds are changed.
- All outputs stay under `standalone/tripo3d-light-test/output/` or the Actions artifact.
