# Pavlov BO3 Nacht scene reference

This directory is the persisted metadata reference recovered from the public Pavlov
Workshop Nacht port audit. It is intentionally **not** the third-party PAK or a dump
of BO3/Pavlov binary assets.

Verified source audit:

- Workshop item: 2755515831
- map: `Nacht_de_Untoten.umap`
- 10,791 scene instances
- 492 unique referenced meshes
- 12 barricades
- 21 zombie spawns
- 9 purchase slots
- 3 canonical zones

The runtime branch uses this reference to know what the real scene should contain.
`tools/maps/audit_nacht_visual_payload.py` resolves the 492 mesh package paths
against either an extracted content root or an UnrealPak list. Strict mode fails on
even one missing referenced UAsset. Stock NZ:P geometry or textures are never counted
as BO3 visual completion.

Examples:

```bash
python3 tools/maps/audit_nacht_visual_payload.py --self-check

python3 tools/maps/audit_nacht_visual_payload.py \
  --pak-index /path/to/WindowsNoEditor-pak-list.txt \
  --strict

python3 tools/maps/audit_nacht_visual_payload.py \
  --content-root /path/to/extracted-pak-root \
  --strict
```
