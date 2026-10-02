from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from tools.hayuya3d.glb_images import write_glb
from tools.hayuya3d.texture_gate import embedded_images
from tools.hayuya3d.texture_superres import (
    build_realesrgan_command,
    required_scale,
    superresolve_basecolor_glb,
)


def png_bytes(size,color):
    buf=io.BytesIO()
    Image.new("RGB",size,color).save(buf,format="PNG")
    return buf.getvalue()


def build_fixture(path:Path):
    base=png_bytes((64,32),(120,70,50))
    normal=png_bytes((32,32),(128,128,255))
    blob=bytearray()
    offsets=[]
    for payload in (base,normal):
        while len(blob)%4:
            blob.append(0)
        offsets.append(len(blob))
        blob.extend(payload)
    doc={
        "asset":{"version":"2.0"},
        "buffers":[{"byteLength":len(blob)}],
        "bufferViews":[
            {"buffer":0,"byteOffset":offsets[0],"byteLength":len(base)},
            {"buffer":0,"byteOffset":offsets[1],"byteLength":len(normal)},
        ],
        "images":[
            {"bufferView":0,"mimeType":"image/png"},
            {"bufferView":1,"mimeType":"image/png"},
        ],
        "textures":[{"source":0},{"source":1}],
        "materials":[{
            "pbrMetallicRoughness":{"baseColorTexture":{"index":0}},
            "normalTexture":{"index":1},
        }],
        "scenes":[{"nodes":[]}],
        "scene":0,
    }
    write_glb(path,doc,bytes(blob))


class TextureSuperresTests(unittest.TestCase):
    def test_required_scale_uses_smallest_supported_scale_that_reaches_target(self):
        self.assertEqual(required_scale(2048,4096),2)
        self.assertEqual(required_scale(1024,4096),4)
        self.assertEqual(required_scale(3000,4096),2)
        self.assertEqual(required_scale(4096,4096),1)

    def test_command_is_explicit_about_scale_model_and_png(self):
        cmd=build_realesrgan_command(
            Path("/opt/realesrgan"),
            Path("/tmp/in.png"),
            Path("/tmp/out.png"),
            scale=2,
            model="realesrgan-x4plus",
            tile_size=256,
        )
        self.assertEqual(cmd[0],"/opt/realesrgan")
        self.assertEqual(cmd[cmd.index("-s")+1],"2")
        self.assertEqual(cmd[cmd.index("-n")+1],"realesrgan-x4plus")
        self.assertEqual(cmd[cmd.index("-m")+1],"/opt/models")
        self.assertEqual(cmd[cmd.index("-t")+1],"256")
        self.assertEqual(cmd[cmd.index("-f")+1],"png")

    def test_missing_runtime_keeps_original_and_reports_unresolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/"source.glb"
            output=root/"output.glb"
            build_fixture(source)
            with mock.patch(
                "tools.hayuya3d.texture_superres.find_realesrgan",
                return_value=None,
            ):
                result=superresolve_basecolor_glb(
                    source,output,target_edge=128
                )
            self.assertFalse(result.attempted)
            self.assertFalse(result.ready)
            self.assertEqual(result.remaining_image_indices,[0])
            self.assertEqual(source.read_bytes(),output.read_bytes())

    def test_superresolution_rewrites_only_basecolor_and_meets_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/"source.glb"
            output=root/"output.glb"
            fake_exe=root/"realesrgan"
            fake_exe.write_text("stub",encoding="utf-8")
            build_fixture(source)

            original={idx:data for idx,mime,data,roles in embedded_images(source)}

            def fake_run(cmd,check):
                src=Path(cmd[cmd.index("-i")+1])
                dst=Path(cmd[cmd.index("-o")+1])
                scale=int(cmd[cmd.index("-s")+1])
                with Image.open(src) as image:
                    up=image.resize(
                        (image.width*scale,image.height*scale),
                        Image.Resampling.NEAREST,
                    )
                    up.save(dst,format="PNG")
                return mock.Mock(returncode=0)

            with mock.patch(
                "tools.hayuya3d.texture_superres.find_realesrgan",
                return_value=fake_exe,
            ), mock.patch(
                "tools.hayuya3d.texture_superres.subprocess.run",
                side_effect=fake_run,
            ):
                result=superresolve_basecolor_glb(
                    source,
                    output,
                    target_edge=128,
                )

            self.assertTrue(result.attempted)
            self.assertTrue(result.ready,result.error)
            self.assertEqual(
                result.method,
                "realesrgan_ncnn_vulkan_basecolor_v2",
            )
            self.assertEqual(result.remaining_image_indices,[])
            self.assertEqual(len(result.items),1)
            self.assertEqual(result.items[0].image_index,0)
            self.assertEqual(result.items[0].final_width,128)
            self.assertEqual(result.items[0].final_height,64)
            self.assertLess(result.items[0].content_mae,1.0)
            self.assertLess(result.items[0].luminance_mean_drift,1.0)
            self.assertTrue(result.items[0].alpha_preserved)

            rewritten={idx:(data,roles) for idx,mime,data,roles in embedded_images(output)}
            with Image.open(io.BytesIO(rewritten[0][0])) as image:
                self.assertEqual(image.size,(128,64))
            self.assertEqual(rewritten[0][1],["baseColor"])
            self.assertEqual(rewritten[1][1],["normal"])
            self.assertEqual(rewritten[1][0],original[1])

    def test_superresolution_rejects_catastrophic_content_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/"source.glb"
            output=root/"output.glb"
            fake_exe=root/"realesrgan"
            fake_exe.write_text("stub",encoding="utf-8")
            build_fixture(source)
            original=source.read_bytes()

            def fake_run(cmd,check):
                src=Path(cmd[cmd.index("-i")+1])
                dst=Path(cmd[cmd.index("-o")+1])
                scale=int(cmd[cmd.index("-s")+1])
                with Image.open(src) as image:
                    corrupted=Image.new(
                        "RGB",
                        (image.width*scale,image.height*scale),
                        (0,255,255),
                    )
                    corrupted.save(dst,format="PNG")
                return mock.Mock(returncode=0)

            with mock.patch(
                "tools.hayuya3d.texture_superres.find_realesrgan",
                return_value=fake_exe,
            ), mock.patch(
                "tools.hayuya3d.texture_superres.subprocess.run",
                side_effect=fake_run,
            ):
                result=superresolve_basecolor_glb(
                    source,
                    output,
                    target_edge=128,
                )

            self.assertTrue(result.attempted)
            self.assertFalse(result.ready)
            self.assertEqual(result.method,"realesrgan_failed")
            self.assertIn("super-resolution content drift",result.error or "")
            self.assertEqual(result.remaining_image_indices,[0])
            self.assertEqual(output.read_bytes(),original)

    def test_superresolution_rejects_wrong_generated_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/"source.glb"
            output=root/"output.glb"
            fake_exe=root/"realesrgan"
            fake_exe.write_text("stub",encoding="utf-8")
            build_fixture(source)

            def fake_run(cmd,check):
                src=Path(cmd[cmd.index("-i")+1])
                dst=Path(cmd[cmd.index("-o")+1])
                scale=int(cmd[cmd.index("-s")+1])
                with Image.open(src) as image:
                    wrong=Image.new(
                        "RGB",
                        (image.width*scale,image.height*scale+1),
                        (120,70,50),
                    )
                    wrong.save(dst,format="PNG")
                return mock.Mock(returncode=0)

            with mock.patch(
                "tools.hayuya3d.texture_superres.find_realesrgan",
                return_value=fake_exe,
            ), mock.patch(
                "tools.hayuya3d.texture_superres.subprocess.run",
                side_effect=fake_run,
            ):
                result=superresolve_basecolor_glb(
                    source,
                    output,
                    target_edge=128,
                )

            self.assertFalse(result.ready)
            self.assertEqual(result.method,"realesrgan_failed")
            self.assertIn(
                "super-resolution dimensions unexpected",
                result.error or "",
            )


if __name__=="__main__":
    unittest.main()
