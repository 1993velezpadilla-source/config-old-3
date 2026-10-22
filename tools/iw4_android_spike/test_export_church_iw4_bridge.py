#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import struct
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "export_church_iw4_bridge.py"
spec = importlib.util.spec_from_file_location("export_church_iw4_bridge", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def make_fixture(path: Path) -> None:
    vertices = [
        (0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 255, 255, 255, 255),
        (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0, 255, 255, 255, 255),
        (0.0, 0.0, 1.0, 0.0, 1.0, 0.0, 0.0, 1.0, 255, 255, 255, 255),
    ]
    indices = [0, 1, 2]
    texture = b"textures/xziel/sanctum/mat_test"
    texture_field = texture + b"\0" * (96 - len(texture))

    with path.open("wb") as out:
        out.write(module.FILE_HEADER.pack(b"XZSM", 4, 1, 3, 3))
        out.write(
            module.BATCH_HEADER.pack(
                3,
                3,
                texture_field,
                1,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                1.0,
            )
        )
        for vertex in vertices:
            out.write(module.VERTEX.pack(*vertex))
        out.write(struct.pack("<3H", *indices))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="iw4-bridge-test-") as tmp:
        root = Path(tmp)
        xzsm = root / "sanctum.xzsm"
        out_dir = root / "bridge"
        make_fixture(xzsm)

        manifest = module.export_bridge(xzsm, out_dir, "xziel_sanctum")
        assert manifest["source"]["batchCount"] == 1
        assert manifest["source"]["totalTriangles"] == 1
        assert manifest["containsProprietaryGamePayload"] is False
        assert manifest["collision"]["required"] is True

        chunk = manifest["visualChunks"][0]
        assert chunk["triangleCount"] == 1
        assert chunk["doubleSided"] is True
        assert chunk["collisionAuthority"] is False

        obj = (out_dir / chunk["obj"]).read_text(encoding="utf-8")
        assert "v 1 0 0" in obj
        assert "vt 1 0" in obj
        assert "vn 0 1 0" in obj
        assert "f 1/1/1 2/2/2 3/3/3" in obj

        saved = json.loads(
            (out_dir / "iw4_bridge_manifest.json").read_text(encoding="utf-8")
        )
        assert saved["mapName"] == "xziel_sanctum"

    print("IW4 church bridge staging gate: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
