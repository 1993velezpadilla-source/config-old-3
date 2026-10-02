from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HAYUYA_DIR = ROOT / "tools" / "hayuya3d"
sys.path.insert(0, str(HAYUYA_DIR))

from gltf_audit import audit_glb


def write_json_only_glb(path: Path, doc: dict) -> None:
    raw = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    raw += b" " * ((4 - len(raw) % 4) % 4)
    total = 12 + 8 + len(raw)
    blob = (
        b"glTF"
        + struct.pack("<II", 2, total)
        + struct.pack("<II", len(raw), 0x4E4F534A)
        + raw
    )
    path.write_bytes(blob)


class GltfAuditTests(unittest.TestCase):
    def _rigged_doc(self):
        return {
            "asset": {"version": "2.0"},
            "accessors": [
                {"count": 4, "type": "VEC3", "componentType": 5126},
                {"count": 4, "type": "VEC4", "componentType": 5123},
                {"count": 4, "type": "VEC4", "componentType": 5126},
                {"count": 2, "type": "MAT4", "componentType": 5126},
            ],
            "meshes": [{
                "primitives": [{
                    "attributes": {
                        "POSITION": 0,
                        "JOINTS_0": 1,
                        "WEIGHTS_0": 2,
                    }
                }]
            }],
            "nodes": [
                {"name": "root", "children": [1]},
                {"name": "spine"},
                {"name": "body", "mesh": 0, "skin": 0},
            ],
            "skins": [{
                "joints": [0, 1],
                "skeleton": 0,
                "inverseBindMatrices": 3,
            }],
            "animations": [{
                "samplers": [{"input": 0, "output": 0}],
                "channels": [{"sampler": 0, "target": {"node": 1, "path": "rotation"}}],
            }],
            "materials": [{
                "pbrMetallicRoughness": {
                    "baseColorFactor": [1, 1, 1, 1],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.8,
                },
                "normalTexture": {"index": 0},
                "occlusionTexture": {"index": 0},
            }],
            "textures": [{"source": 0}],
            "images": [{"uri": "dummy.png"}],
        }

    def test_valid_rig_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rig.glb"
            write_json_only_glb(path, self._rigged_doc())
            report = audit_glb(path)
            self.assertTrue(report.valid_glb)
            self.assertTrue(report.rig_ready)
            self.assertTrue(report.animation_ready)
            self.assertEqual(report.skin_count, 1)
            self.assertEqual(report.joint_count, 2)
            self.assertEqual(report.skinned_mesh_nodes, 1)
            for channel in ("baseColor", "metallic", "roughness", "normal", "occlusion"):
                self.assertIn(channel, report.material_channels)

    def test_valid_morph_targets_are_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc=self._rigged_doc()
            doc["accessors"].append(
                {"count":4,"type":"VEC3","componentType":5126}
            )
            primitive=doc["meshes"][0]["primitives"][0]
            primitive["targets"]=[{"POSITION":4}]
            doc["meshes"][0]["weights"]=[0.0]
            doc["nodes"][2]["weights"]=[0.0]
            doc["animations"][0]["channels"].append({
                "sampler":0,
                "target":{"node":2,"path":"weights"},
            })
            path=Path(tmp)/"morph.glb"
            write_json_only_glb(path,doc)
            report=audit_glb(path)
            self.assertTrue(report.valid_glb)
            self.assertTrue(report.morph_ready,report.errors)
            self.assertEqual(report.morph_mesh_count,1)
            self.assertEqual(report.morph_primitive_count,1)
            self.assertEqual(report.morph_target_count,1)

    def test_morph_accessor_count_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc=self._rigged_doc()
            doc["accessors"].append(
                {"count":3,"type":"VEC3","componentType":5126}
            )
            doc["meshes"][0]["primitives"][0]["targets"]=[
                {"POSITION":4}
            ]
            doc["meshes"][0]["weights"]=[0.0]
            path=Path(tmp)/"bad-morph-count.glb"
            write_json_only_glb(path,doc)
            report=audit_glb(path)
            self.assertFalse(report.morph_ready)
            self.assertTrue(
                any("!= POSITION" in item for item in report.errors),
                report.errors,
            )

    def test_mesh_morph_weight_length_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc=self._rigged_doc()
            doc["accessors"].append(
                {"count":4,"type":"VEC3","componentType":5126}
            )
            doc["meshes"][0]["primitives"][0]["targets"]=[
                {"POSITION":4}
            ]
            doc["meshes"][0]["weights"]=[0.0,0.0]
            path=Path(tmp)/"bad-morph-weights.glb"
            write_json_only_glb(path,doc)
            report=audit_glb(path)
            self.assertFalse(report.morph_ready)
            self.assertTrue(
                any("weights length" in item for item in report.errors),
                report.errors,
            )

    def test_weight_animation_without_morph_target_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc=self._rigged_doc()
            doc["animations"][0]["channels"].append({
                "sampler":0,
                "target":{"node":2,"path":"weights"},
            })
            path=Path(tmp)/"bad-weight-animation.glb"
            write_json_only_glb(path,doc)
            report=audit_glb(path)
            self.assertFalse(report.morph_ready)
            self.assertTrue(
                any("without morph targets" in item for item in report.errors),
                report.errors,
            )

    def test_inverse_bind_mismatch_rejects_rig(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = self._rigged_doc()
            doc["accessors"][3]["count"] = 1
            path = Path(tmp) / "bad.glb"
            write_json_only_glb(path, doc)
            report = audit_glb(path)
            self.assertFalse(report.rig_ready)
            self.assertTrue(any("inverseBindMatrices count" in x for x in report.errors))

    def test_unrigged_asset_is_valid_but_not_rig_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = {
                "asset": {"version": "2.0"},
                "meshes": [{"primitives": [{"attributes": {}}]}],
                "nodes": [{"mesh": 0}],
            }
            path = Path(tmp) / "plain.glb"
            write_json_only_glb(path, doc)
            report = audit_glb(path)
            self.assertTrue(report.valid_glb)
            self.assertFalse(report.rig_ready)
            self.assertEqual(report.skin_count, 0)
            self.assertTrue(any("unrigged" in x for x in report.warnings))


if __name__ == "__main__":
    unittest.main()
