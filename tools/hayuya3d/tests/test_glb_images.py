from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.hayuya3d.glb_images import read_glb, replace_embedded_images, write_glb
from tools.hayuya3d.texture_gate import embedded_images


def png_bytes(size, color):
    buf=io.BytesIO()
    Image.new("RGB",size,color).save(buf,format="PNG")
    return buf.getvalue()


def build_fixture(path:Path):
    geometry=b"GEOMETRY_SENTINEL_1234567890"
    base=png_bytes((32,32),(120,70,50))
    normal=png_bytes((16,16),(128,128,255))

    # Keep geometry first so the test can prove its original bytes/offset never move.
    blob=bytearray(geometry)
    while len(blob)%4:
        blob.append(0)
    base_offset=len(blob)
    blob.extend(base)
    while len(blob)%4:
        blob.append(0)
    normal_offset=len(blob)
    blob.extend(normal)

    doc={
        "asset":{"version":"2.0"},
        "buffers":[{"byteLength":len(blob)}],
        "bufferViews":[
            {"buffer":0,"byteOffset":0,"byteLength":len(geometry)},
            {"buffer":0,"byteOffset":base_offset,"byteLength":len(base)},
            {"buffer":0,"byteOffset":normal_offset,"byteLength":len(normal)},
        ],
        "images":[
            {"bufferView":1,"mimeType":"image/png","name":"base"},
            {"bufferView":2,"mimeType":"image/png","name":"normal"},
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
    return geometry,base,normal


class GlbImageRewriteTests(unittest.TestCase):
    def test_replacement_appends_image_without_moving_existing_buffers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/"source.glb"
            output=root/"output.glb"
            geometry,base,normal=build_fixture(source)
            replacement=png_bytes((64,64),(130,75,55))

            source_doc,source_bin=read_glb(source)
            result=replace_embedded_images(
                source,
                output,
                {0:("image/png",replacement)},
            )
            output_doc,output_bin=read_glb(output)

            self.assertEqual(output_bin[:len(geometry)],geometry)
            self.assertEqual(
                output_doc["bufferViews"][:3],
                source_doc["bufferViews"][:3],
            )
            self.assertEqual(
                output_bin[
                    source_doc["bufferViews"][2]["byteOffset"]:
                    source_doc["bufferViews"][2]["byteOffset"]+
                    source_doc["bufferViews"][2]["byteLength"]
                ],
                normal,
            )
            self.assertNotEqual(
                output_doc["images"][0]["bufferView"],
                source_doc["images"][0]["bufferView"],
            )
            self.assertEqual(
                output_doc["images"][1]["bufferView"],
                source_doc["images"][1]["bufferView"],
            )
            self.assertGreater(result["appended_bytes"],len(replacement)-4)

            metrics={idx:(mime,data,roles) for idx,mime,data,roles in embedded_images(output)}
            self.assertEqual(metrics[0][2],["baseColor"])
            self.assertEqual(metrics[1][2],["normal"])
            with Image.open(io.BytesIO(metrics[0][1])) as image:
                self.assertEqual(image.size,(64,64))
            with Image.open(io.BytesIO(metrics[1][1])) as image:
                self.assertEqual(image.size,(16,16))


if __name__=="__main__":
    unittest.main()
