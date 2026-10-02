from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.hayuya3d.material_rebake import (
    build_normal_rebake_command,
    rebake_material_channels,
)


class MaterialRebakeTests(unittest.TestCase):
    def test_normal_rebake_command_is_explicit_and_bounded(self):
        cmd=build_normal_rebake_command(
            Path("/opt/blender"),
            Path("/tmp/source.glb"),
            Path("/tmp/target.glb"),
            Path("/tmp/output.glb"),
            Path("/tmp/report.json"),
            size=4096,
        )
        self.assertEqual(cmd[0],"/opt/blender")
        self.assertIn("--background",cmd)
        self.assertIn("blender_material_rebake.py"," ".join(cmd))
        self.assertEqual(cmd[-2:],[ "--size","4096" ])

    def test_missing_blender_keeps_normal_and_ao_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/"source.glb"
            target=root/"target.glb"
            output=root/"output.glb"
            source.write_bytes(b"glTF"+b"s"*512)
            target.write_bytes(b"glTF"+b"t"*512)

            with mock.patch("tools.hayuya3d.material_rebake.find_blender",return_value=None):
                result=rebake_material_channels(
                    source,target,output,
                    required=["normal","occlusion"],
                    max_texture_size=4096,
                )

            self.assertFalse(result.attempted)
            self.assertEqual(result.resolved_channels,[])
            self.assertEqual(result.remaining_channels,["normal","occlusion"])
            self.assertEqual(output.read_bytes(),target.read_bytes())

    def test_no_requested_supported_channel_is_copy_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/"source.glb"
            target=root/"target.glb"
            output=root/"output.glb"
            source.write_bytes(b"glTF"+b"s"*512)
            target.write_bytes(b"glTF"+b"t"*512)
            result=rebake_material_channels(
                source,target,output,
                required=["occlusion"],
                max_texture_size=2048,
                blender=None,
            )
            self.assertFalse(result.attempted)
            self.assertEqual(result.remaining_channels,["occlusion"])
            self.assertEqual(output.read_bytes(),target.read_bytes())


if __name__=="__main__":
    unittest.main()
