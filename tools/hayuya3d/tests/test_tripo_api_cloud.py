#!/usr/bin/env python3
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HAYUYA3D = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HAYUYA3D))

import tripo_api_cloud as mod

class Response:
    def __init__(self, payload=None, raw=None, status=200):
        self._payload = payload
        self.raw = io.BytesIO(raw or b"")
        self.status_code = status
        self.headers = {}
        self.text = ""

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

class Session:
    def post(self, url, **_kwargs):
        if url.endswith("/upload"):
            return Response({"code": 0, "data": {"image_token": "abc"}})
        return Response({"code": 0, "data": {"task_id": "t1"}})

    def get(self, url, **_kwargs):
        if url.endswith("/user/balance"):
            return Response(
                {"code": 0, "data": {"balance": 100, "frozen": 0}}
            )
        if "/task/" in url:
            return Response(
                {
                    "code": 0,
                    "data": {
                        "status": "success",
                        "progress": 100,
                        "output": {"pbr_model": "https://cdn/x.glb"},
                    },
                }
            )
        return Response(raw=b"glTF" + b"0" * 2048)

class TripoAPICloudTests(unittest.TestCase):
    def test_single_image_prefers_pbr_model(self):
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / "source.jpg"
            image.write_bytes(b"x")
            output = Path(temp) / "result.glb"
            with patch.object(mod.requests, "Session", return_value=Session()):
                meta = mod.generate(image, output, api_key="tsk_test")
            self.assertEqual(output.read_bytes()[:4], b"glTF")
            self.assertEqual(meta["provider"], "tripoapi")
            self.assertEqual(meta["artifact_kind"], "pbr_model")
            self.assertFalse(meta["multi_view"])

    def test_v31_ultra_payload_keeps_max_geometry_and_omits_false_quad(self):
        data = mod._base_task_options(
            model_version="v3.1-20260211",
            seed=1993,
            texture=True,
            pbr=True,
            texture_quality="standard",
            face_limit=2_000_000,
            geometry_quality="detailed",
            quad=False,
            auto_size=False,
        )
        self.assertEqual(data["face_limit"], 2_000_000)
        self.assertEqual(data["geometry_quality"], "detailed")
        self.assertNotIn("quad", data)
        self.assertNotIn("auto_size", data)

    def test_p1_capability_filter_removes_unsupported_params(self):
        data = mod._base_task_options(
            model_version="P1-20260311",
            seed=1993,
            texture=True,
            pbr=True,
            texture_quality="standard",
            face_limit=2_000_000,
            geometry_quality="detailed",
            quad=True,
            auto_size=True,
        )
        self.assertEqual(data["face_limit"], 20_000)
        self.assertNotIn("geometry_quality", data)
        self.assertNotIn("quad", data)
        self.assertNotIn("auto_size", data)

    def test_budget_profiles_prioritize_geometry(self):
        self.assertEqual(mod._budget_profile(50)["name"], "ultra_pbr")
        self.assertEqual(
            mod._budget_profile(40)["name"], "ultra_geometry_only"
        )
        self.assertEqual(mod._budget_profile(30)["name"], "standard_pbr")
        self.assertEqual(
            mod._budget_profile(20)["name"], "standard_geometry_only"
        )
        with self.assertRaises(mod.TripoUnavailable):
            mod._budget_profile(19.999)

    def test_standard_v31_clamps_faces_to_1_5m(self):
        data = mod._base_task_options(
            model_version="v3.1-20260211",
            seed=1993,
            texture=False,
            pbr=False,
            texture_quality="standard",
            face_limit=2_000_000,
            geometry_quality="standard",
            quad=False,
            auto_size=False,
        )
        self.assertEqual(data["face_limit"], 1_500_000)

    def test_multiview_preserves_front_left_back_right_slots(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = []
            for name in ("front", "left", "right"):
                path = Path(temp) / f"{name}.jpg"
                path.write_bytes(b"x")
                paths.append(path)

            captured = {}

            def upload(path, **_kwargs):
                return {"type": "jpg", "file_token": Path(path).stem}

            def create(data, **_kwargs):
                captured.update(data)
                return "t2"

            def wait(*_args, **_kwargs):
                return {
                    "status": "success",
                    "output": {"model": "https://cdn/x.glb"},
                }

            def download(_task, out, **_kwargs):
                Path(out).write_bytes(b"glTF" + b"0" * 2048)
                return ("model", "https://cdn/x.glb")

            with (
                patch.object(
                    mod,
                    "get_balance",
                    return_value={"balance": 100.0, "frozen": 0.0},
                ),
                patch.object(mod, "upload_image", side_effect=upload),
                patch.object(mod, "create_task", side_effect=create),
                patch.object(mod, "wait_for_task", side_effect=wait),
                patch.object(mod, "download_best_model", side_effect=download),
            ):
                meta = mod.generate_multiview(
                    [paths[0], paths[1], None, paths[2]],
                    Path(temp) / "mv.glb",
                    api_key="tsk_test",
                )

            self.assertEqual(captured["type"], "multiview_to_model")
            self.assertEqual(captured["files"][0]["file_token"], "front")
            self.assertEqual(captured["files"][1]["file_token"], "left")
            self.assertEqual(captured["files"][2], {})
            self.assertEqual(captured["files"][3]["file_token"], "right")
            self.assertEqual(
                meta["view_order"], ["front", "left", "back", "right"]
            )

if __name__ == "__main__":
    unittest.main()
