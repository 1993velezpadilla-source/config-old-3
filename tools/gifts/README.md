# Xogot split gift runtime

The eight user-provided Tripo GLBs are authoring sheets, not runtime props.
They were spatially separated into **104 complete models** with **14,986,049
triangles conserved exactly**.

Runtime layout:

```
xogot/assets/gifts_split/
  altar/Model_01.glb ... Model_09.glb
  candleholders/Model_01.glb ... Model_19.glb
  chandeliers/Model_01.glb ... Model_11.glb
  furniture/Model_01.glb ... Model_12.glb
  ruins/Model_01.glb ... Model_29.glb
  stained_multi/Model_01.glb ... Model_11.glb
  stained_single/Model_01.glb
  statues/Model_01.glb ... Model_12.glb
```

Each bundle keeps the original 4096×4096 Color/ORM/NormalGL images unchanged,
but stores them once in that bundle's `textures/` directory. No decimation,
texture resize, or image recompression is allowed.

The local runtime was repacked into eight independent ZIP archives. Their exact
byte sizes and SHA-256 digests live in
`xogot/assets/gifts/gift_runtime_pack_manifest.json`.

Install with:

```bash
python tools/gifts/install_runtime_packs.py \
  --packs-dir /path/to/gift_runtime_packs \
  --project-root xogot
```

The installer refuses corrupted, incomplete, or wrong-version packs. The game
never falls back to spawning the original fused source sheets.
