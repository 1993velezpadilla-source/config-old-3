# UE → Xogot Bridge

This directory is the engine-neutral Unreal authority bridge used by Xogot.

The first bridge slice is **Cascade cooked distribution reconstruction**. It
turns UE4 `FDistributionLookupTable` payloads already extracted by CUE4Parse
into stable JSON semantics:

- constant
- uniform
- constant curve
- uniform curve
- scalar and FVector distributions
- UE lookup-table time reconstruction

The implementation is intentionally separate from Godot rendering. This gives
the project a second authority layer: if a Godot particle bridge interprets a
cooked distribution differently, CI can detect the disagreement before a
screenshot is used as proof.

## Reference implementations

The semantic model is informed by:

- JsonAsAsset/Reflection — `ParticleSystemDecooking.h` (MIT), which reconstructs
  cooked Cascade raw distributions.
- UE4 `ERawDistributionOperation` / `FDistributionLookupTable` layout.
- CUE4Parse remains the binary/package extraction authority.

No third-party source is vendored here. The bridge is an independent
engine-neutral implementation with its own tests.

## Run

```bash
python3 tools/ue_bridge/test_cascade_distribution_decoder.py
python3 tools/ue_bridge/cascade_distribution_decoder.py \
  --graphs nacht-particle-graphs.json \
  --out cascade-distribution-report.json \
  --strict
```

A GREEN report does **not** claim visual 1:1 parity. It proves that cooked
distribution lookup tables can be reconstructed deterministically without
case-by-case guesses.
