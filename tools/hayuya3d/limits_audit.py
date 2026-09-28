#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "hayuya" / "standards" / "hayuya_3d_aaa_limits_v1.json"


def main() -> int:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    contract = spec["hayuya_aaa_contract"]
    tripo = spec["tripo_parity_reference"]
    backend = spec["backend_limits"]

    # Import the live profile table so this report fails if the code drifts away
    # from the committed AAA contract.
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import hayuya

    ultra = hayuya.PROFILES["ultra"]
    if int(ultra.hero_faces) != int(contract["hero_triangle_target"]):
        raise SystemExit(
            "HAYUYA_LIMIT_AUDIT_FAIL "
            f"ultra.hero_faces={ultra.hero_faces} "
            f"contract={contract['hero_triangle_target']}"
        )

    report = {
        "schema": 1,
        "product": "HAYUYA 3D",
        "scope": spec["scope"],
        "configured_max": {
            "hero_triangles": int(contract["hero_triangle_hard_ceiling"]),
            "vertices": contract["vertex_hard_ceiling"],
            "vertex_policy": contract["vertex_policy"],
        },
        "tripo_parity": {
            "documented_max_triangles": int(
                tripo["documented_triangle_face_limit_ultra"]
            ),
            "documented_max_vertices": tripo["documented_vertex_limit"],
            "observed_benchmark_triangles": int(
                tripo["observed_benchmark"]["triangles"]
            ),
            "observed_benchmark_vertices": int(
                tripo["observed_benchmark"]["vertices"]
            ),
        },
        "provider_constraints": {
            "trellis2_public_hf_faces": int(
                backend["trellis2_public_hf_space"]["extraction_face_ceiling"]
            ),
            "trellis2_direct_target_faces": int(
                backend["trellis2_open_source_direct"]["requested_face_ceiling"]
            ),
            "trellis2_internal_preview_safety_faces": int(
                backend["trellis2_open_source_direct"][
                    "internal_preview_safety_face_count"
                ]
            ),
            "triposg_simplified": bool(
                backend["triposg_open_source"]["simplify"]
            ),
            "triposg_face_limit": backend["triposg_open_source"][
                "configured_face_limit"
            ],
            "triposf_voxel_resolution": int(
                backend["triposf_open_source"]["voxel_resolution_max"]
            ),
        },
        "profiles": {
            name: {
                "runtime_faces": int(profile.faces),
                "hero_faces": int(profile.hero_faces),
                "texture_size": int(profile.texture_size),
                "trellis2_resolution": int(profile.trellis2_resolution),
            }
            for name, profile in hayuya.PROFILES.items()
        },
    }
    print("HAYUYA_LIMIT_AUDIT_GREEN")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
