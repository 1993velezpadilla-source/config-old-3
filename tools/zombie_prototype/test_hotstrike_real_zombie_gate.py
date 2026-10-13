#!/usr/bin/env python3
"""Regression tests: green engine capacity must never masquerade as new art."""
import hashlib
import io
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from guard_hotstrike_real_zombie import (
    ProvenanceError, mdl_header, verify_real_conversion,
    verify_author_source, verify_png, verify,
)


def mdl(verts, tris, frames):
    data = bytearray(84)
    data[:4] = b"IDPO"
    struct.pack_into("<i", data, 4, 6)
    struct.pack_into("<6i", data, 48, 4, 1024, 1024, verts, tris, frames)
    return bytes(data) + b"fixture "


def png():
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + struct.pack(">II", 2048, 2048) + b"\x08\x02\x00\x00\x00"


class ZombieSourceRegressionTest(unittest.TestCase):
    def test_stock_geometry_is_rejected(self):
        old = mdl(1000, 484, 211)
        with self.assertRaisesRegex(ProvenanceError, "low-detail"):
            verify_real_conversion(old, old)

    def test_real_author_triangle_count_must_not_be_rejected(self):
        # Blender verified the authentic author FBX has 8,284 triangles too.
        self.assertEqual(verify_real_conversion(mdl(4143,8284,211),
                         mdl(389,484,211))["triangles"],8284)

    def test_known_synthetic_is_rejected_by_sha(self):
        # The exact stock stress model fingerprint is checked in the guard;
        # we also test the specific SHA match via a mocked sha() call because
        # its 8,189-vertex, 211-frame serialized MDL is huge.
        from unittest.mock import patch
        from guard_hotstrike_real_zombie import KNOWN_STOCK_SYNTHETIC_MDL_SHA256
        with patch("guard_hotstrike_real_zombie.sha",return_value=KNOWN_STOCK_SYNTHETIC_MDL_SHA256):
            with self.assertRaisesRegex(ProvenanceError, "synthetic benchmark"):
                verify_real_conversion(mdl(8189,8284,211),mdl(389,484,211))

    def test_t_pose_is_rejected_even_with_genuine_complex_geometry(self):
        with self.assertRaisesRegex(ProvenanceError, "T-pose"):
            verify_real_conversion(mdl(4200, 8286, 1), mdl(1000, 484, 211))

    def test_animated_mesh_header_can_pass_prefilter_not_device(self):
        actual = verify_real_conversion(mdl(4200, 8286, 211), mdl(1000, 484, 211))
        self.assertEqual(actual["triangles"], 8286)
        self.assertEqual(actual["frames"], 211)
        self.assertEqual(verify_png(png())["width"], 2048)

    def test_author_source_must_have_mesh_and_textures(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "SZombie.zip"
            with ZipFile(path, "w") as z:
                z.writestr("model.fbx", b"FBX")
            with self.assertRaisesRegex(ProvenanceError, "PBR textures"):
                verify_author_source(path)
            with ZipFile(path, "a") as z:
                z.writestr("albedo.png", png())
            self.assertEqual(verify_author_source(path)["texture_count"], 1)

    def test_packaged_renderer_and_actual_model_must_match(self):
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            (d / "original.mdl").write_bytes(mdl(1000, 484, 211))
            converted = mdl(4200, 8286, 211)
            (d / "converted.mdl").write_bytes(converted)
            (d / "texture.png").write_bytes(png())
            with ZipFile(d / "source.zip", "w") as z:
                z.writestr("source_zombie.fbx", b"authored file fixture")
                z.writestr("textures/base.png", png())
            game_stream = io.BytesIO()
            with ZipFile(game_stream, "w") as z:
                z.writestr("nzp/models/ai/zfull.mdl", converted)
                z.writestr("nzp/models/ai/xziel_zombie_hd_0.png", png())
            apk = d / "test.apk"
            with ZipFile(apk, "w") as z:
                z.writestr("assets/nzp-data.zip", game_stream.getvalue())
                z.writestr("lib/arm64-v8a/libmain.so",
                           b"XZIEL_ZOMBIE_HD: skin= marker")
            result = verify(d/"source.zip", d/"original.mdl", d/"converted.mdl",
                            d/"texture.png", apk)
            self.assertEqual(result["result"], "PACKAGING_PROVENANCE_PASS_NOT_DEVICE_GREEN")
            self.assertTrue(result["not_verified"])
            with ZipFile(apk, "w") as z:
                z.writestr("assets/nzp-data.zip", game_stream.getvalue())
                z.writestr("lib/arm64-v8a/libmain.so", b"old renderer only")
            with self.assertRaisesRegex(ProvenanceError, "No native PNG"):
                verify(d/"source.zip", d/"original.mdl", d/"converted.mdl",
                       d/"texture.png", apk)


    def test_installer_overwrites_actual_live_zfull_and_all_skin_slots(self):
        from tools.zombie_hd.install_real_zombie_assets import install
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            stock = mdl(1000, 484, 211)
            new = mdl(4200, 8286, 211)
            (d/"old.mdl").write_bytes(stock)
            (d/"new.mdl").write_bytes(new)
            (d/"albedo.png").write_bytes(png())
            with ZipFile(d/"SZombie.zip", "w") as z:
                z.writestr("source.fbx", b"authored fake fixture only")
                z.writestr("material.png", png())
            data=d/"nzp-data.zip"
            with ZipFile(data, "w") as z:
                z.writestr("nzp/models/ai/zfull.mdl", stock)
                z.writestr("nzp/maps/xziel_proto.bsp", b"DEAD_CELL")
                z.writestr("nzp/models/ai/xziel_zombie_hd_0.png", b"stale")
            report=install(d/"SZombie.zip", d/"old.mdl", d/"new.mdl", d/"albedo.png", data)
            self.assertEqual(report["status"], "REAL_MODEL_STAGED_NOT_DEVICE_VERIFIED")
            with ZipFile(data) as z:
                self.assertEqual(z.read("nzp/models/ai/zfull.mdl"), new)
                self.assertEqual(z.read("nzp/maps/xziel_proto.bsp"), b"DEAD_CELL")
                for i in range(4):
                    p=f"nzp/models/ai/xziel_zombie_hd_{i}.png"
                    self.assertEqual(z.namelist().count(p), 1)
                    self.assertEqual(z.read(p), png())
            self.assertEqual((d/"nzp-data.version").read_text().strip(),
                             hashlib.sha256(data.read_bytes()).hexdigest())



if __name__ == "__main__":
    unittest.main()
