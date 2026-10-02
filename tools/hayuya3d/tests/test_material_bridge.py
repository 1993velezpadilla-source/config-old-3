from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HAYUYA_DIR = ROOT / "tools" / "hayuya3d"
sys.path.insert(0, str(HAYUYA_DIR))

import numpy as np
import trimesh

from material_bridge import transfer_base_color, transfer_best_material
from qa import inspect_mesh


class MaterialBridgeTests(unittest.TestCase):
    def test_pbr_uv_material_survives_topology_transfer(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_path = root / "source_pbr.glb"
            refined_path = root / "refined_plane.glb"
            output_path = root / "bridged_pbr.glb"

            vertices = np.array([
                [-0.5, -0.5, 0.0],
                [ 0.5, -0.5, 0.0],
                [ 0.5,  0.5, 0.0],
                [-0.5,  0.5, 0.0],
            ], dtype=np.float64)
            faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
            uvs = np.array([
                [0.0, 0.0],
                [1.0, 0.0],
                [1.0, 1.0],
                [0.0, 1.0],
            ], dtype=np.float64)

            base = Image.fromarray(np.full((8, 8, 4), [180, 70, 30, 255], dtype=np.uint8), mode="RGBA")
            mr = Image.fromarray(np.full((8, 8, 3), [0, 90, 210], dtype=np.uint8), mode="RGB")
            normal = Image.fromarray(np.full((8, 8, 3), [128, 128, 255], dtype=np.uint8), mode="RGB")
            ao = Image.fromarray(np.full((8, 8), 220, dtype=np.uint8), mode="L")
            emissive = Image.fromarray(np.full((8, 8, 3), [8, 12, 16], dtype=np.uint8), mode="RGB")

            material = trimesh.visual.material.PBRMaterial(
                name="hayuya_pbr_test",
                baseColorTexture=base,
                metallicRoughnessTexture=mr,
                normalTexture=normal,
                occlusionTexture=ao,
                emissiveTexture=emissive,
                metallicFactor=0.85,
                roughnessFactor=0.65,
                emissiveFactor=[1.0, 1.0, 1.0],
                doubleSided=True,
            )
            source = trimesh.Trimesh(
                vertices=vertices,
                faces=faces,
                process=False,
                visual=trimesh.visual.TextureVisuals(uv=uvs, material=material),
            )
            source_path.write_bytes(trimesh.exchange.gltf.export_glb(trimesh.Scene(source)))

            refined_vertices = np.array([
                [-0.5, -0.5, 0.0],
                [ 0.0, -0.5, 0.0],
                [ 0.5, -0.5, 0.0],
                [-0.5,  0.0, 0.0],
                [ 0.0,  0.0, 0.0],
                [ 0.5,  0.0, 0.0],
                [-0.5,  0.5, 0.0],
                [ 0.0,  0.5, 0.0],
                [ 0.5,  0.5, 0.0],
            ], dtype=np.float64)
            refined_faces = np.array([
                [0, 1, 4], [0, 4, 3],
                [1, 2, 5], [1, 5, 4],
                [3, 4, 7], [3, 7, 6],
                [4, 5, 8], [4, 8, 7],
            ], dtype=np.int64)
            refined = trimesh.Trimesh(vertices=refined_vertices, faces=refined_faces, process=False)
            refined_path.write_bytes(trimesh.exchange.gltf.export_glb(trimesh.Scene(refined)))

            result = transfer_best_material(
                source_path,
                refined_path,
                output_path,
                total_samples=6000,
                max_texture_size=64,
            )

            self.assertFalse(result.fallback_used)
            for channel in ("baseColor", "metallic", "roughness", "emissive"):
                self.assertIn(channel, result.channels)
            self.assertNotIn("normal", result.channels)
            self.assertNotIn("occlusion", result.channels)
            self.assertEqual(set(result.dropped_channels or []), {"normal", "occlusion"})
            self.assertEqual(set(result.rebake_required or []), {"normal", "occlusion"})

            loaded = trimesh.load(output_path, force="scene", process=False)
            mesh = list(loaded.geometry.values())[0]
            self.assertIsNotNone(getattr(mesh.visual, "uv", None))
            self.assertEqual(len(mesh.visual.uv), len(mesh.vertices))

            pbr = mesh.visual.material
            self.assertIsNotNone(getattr(pbr, "baseColorTexture", None))
            self.assertIsNotNone(getattr(pbr, "metallicRoughnessTexture", None))
            self.assertIsNone(getattr(pbr, "normalTexture", None))
            self.assertIsNone(getattr(pbr, "occlusionTexture", None))
            self.assertIsNotNone(getattr(pbr, "emissiveTexture", None))

            inspected = inspect_mesh(
                output_path,
                backend="pbr_bridge_test",
                mode="prop",
                target_faces=8,
            )
            self.assertTrue(inspected.valid, f"inspect failed: {inspected.notes}")
            self.assertEqual(
                inspected.material_score,
                85.0,
                f"topology-safe bridge must not receive credit for stripped normal/AO: "
                f"material_score={inspected.material_score} channels={inspected.pbr_channels} notes={inspected.notes}",
            )
            for channel in ("baseColor", "metallic", "roughness", "emissive"):
                self.assertIn(channel, inspected.pbr_channels)
            self.assertNotIn("normal", inspected.pbr_channels)
            self.assertNotIn("occlusion", inspected.pbr_channels)

    def test_topology_safe_bridge_does_not_claim_stale_normal_or_ao(self):
        from PIL import Image
        from material_bridge import sanitize_topology_changed_material

        normal = Image.fromarray(
            np.full((4, 4, 3), [128, 128, 255], dtype=np.uint8),
            mode="RGB",
        )
        ao = Image.fromarray(
            np.full((4, 4), 200, dtype=np.uint8),
            mode="L",
        )
        material = trimesh.visual.material.PBRMaterial(
            baseColorFactor=[200, 160, 120, 255],
            metallicFactor=0.2,
            roughnessFactor=0.7,
            normalTexture=normal,
            occlusionTexture=ao,
        )
        safe, dropped = sanitize_topology_changed_material(material)
        self.assertEqual(set(dropped), {"normal", "occlusion"})
        self.assertIsNone(getattr(safe, "normalTexture", None))
        self.assertIsNone(getattr(safe, "occlusionTexture", None))
        self.assertIsNotNone(getattr(safe, "baseColorFactor", None))

    def test_uniform_source_color_transfers_to_refined_mesh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_path = root / "source.glb"
            refined_path = root / "refined.glb"
            output_path = root / "bridged.glb"

            source = trimesh.creation.box(extents=[1.0, 1.0, 1.0])
            rgba = np.tile(
                np.array([[20, 210, 60, 255]], dtype=np.uint8),
                (len(source.vertices), 1),
            )
            source.visual = trimesh.visual.ColorVisuals(
                source,
                vertex_colors=rgba,
            )
            source_path.write_bytes(
                trimesh.exchange.gltf.export_glb(trimesh.Scene(source))
            )

            refined = trimesh.creation.icosphere(subdivisions=2, radius=0.48)
            refined_path.write_bytes(
                trimesh.exchange.gltf.export_glb(trimesh.Scene(refined))
            )

            result = transfer_base_color(
                source_path,
                refined_path,
                output_path,
                total_samples=5000,
            )
            self.assertTrue(output_path.is_file())
            self.assertEqual(output_path.read_bytes()[:4], b"glTF")
            self.assertGreater(result.sample_count, 1000)

            loaded = trimesh.load(output_path, force="scene", process=False)
            mesh = trimesh.util.concatenate(list(loaded.geometry.values()))
            colors = np.asarray(mesh.visual.vertex_colors[:, :3])
            mean = colors.mean(axis=0)
            self.assertLess(float(mean[0]), 50.0)
            self.assertGreater(float(mean[1]), 170.0)
            self.assertLess(float(mean[2]), 90.0)


if __name__ == "__main__":
    unittest.main()
