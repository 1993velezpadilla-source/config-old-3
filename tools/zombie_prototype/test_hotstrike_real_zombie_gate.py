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

    def test_synthetic_8284_is_explicitly_rejected(self):
        old = mdl(1000, 484, 211)
        fake = mdl(9000, 8284, 211)
        with self.assertRaisesRegex(ProvenanceError, "synthetic benchmark"):
            verify_real_conversion(fake, old)

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


if __name__ == "__main__":
    unittest.main()
