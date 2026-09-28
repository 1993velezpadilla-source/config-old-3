# Nacht Source Fidelity Policy

For the BO3 Nacht parity target, production builds must preserve the highest-quality authored source data available to the project.

Hard rules:

- Do not downscale authored base-color, normal, emissive, mask, lightmap, reflection, or other visual textures for the production parity path.
- Do not decimate or simplify source geometry, substitute a lower LOD, or reduce vertex/index precision to gain performance unless the user explicitly approves that specific quality tradeoff.
- Do not replace authored material detail with lower-resolution stand-ins when the authored source is available.
- Performance work must prefer streaming, mip residency, culling, batching, visibility, cache policy, compressed GPU-native storage, and distance-aware residency while retaining the full source-quality asset.
- Diagnostic experiments may use reduced assets only when they are clearly isolated from the production parity path and cannot silently become the shipping/default configuration.
- CI must fail closed if the production Nacht texture compiler emits authored textures at dimensions smaller than their source dimensions.

The target is visual/gameplay parity, not a mobile-quality reinterpretation.
