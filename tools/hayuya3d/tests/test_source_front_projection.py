import pathlib
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image
import trimesh

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from source_front_projection import project_source_front


class SourceFrontProjectionTests(unittest.TestCase):
    def test_hunyuan_y_up_height_drives_texture_v(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = root / "source.png"
            mesh_path = root / "native.glb"
            output = root / "projected.glb"

            rgba = np.zeros((64, 32, 4), dtype=np.uint8)
            rgba[:, :, 3] = 255
            rgba[:32, :, :3] = (240, 240, 240)
            rgba[32:, :, :3] = (30, 30, 30)
            Image.fromarray(rgba, mode="RGBA").save(source)

            mesh = trimesh.creation.box(extents=[1.0, 2.0, 1.0])
            mesh_path.write_bytes(
                trimesh.exchange.gltf.export_glb(trimesh.Scene(mesh))
            )

            report = project_source_front(
                source,
                mesh_path,
                output,
                texture_edge=128,
            )
            self.assertEqual(report["projection_plane"], "XY")
            self.assertEqual(report["source_mesh_up_axis"], "Y")

            loaded = trimesh.load(output, force="scene", process=False)
            geometries = list(loaded.geometry.values())
            self.assertEqual(len(geometries), 1)
            projected = geometries[0]
            uv = np.asarray(projected.visual.uv, dtype=np.float64)
            vertices = np.asarray(projected.vertices, dtype=np.float64)
            self.assertEqual(len(uv), len(vertices))

            y_norm = (
                (vertices[:, 1] - vertices[:, 1].min())
                / max(float(np.ptp(vertices[:, 1])), 1e-8)
            )
            corr = float(np.corrcoef(y_norm, uv[:, 1])[0, 1])
            self.assertGreater(corr, 0.99)


if __name__ == "__main__":
    unittest.main()
