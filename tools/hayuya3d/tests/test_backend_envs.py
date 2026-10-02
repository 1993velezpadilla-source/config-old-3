from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
HAYUYA_DIR = ROOT / "tools" / "hayuya3d"
sys.path.insert(0, str(HAYUYA_DIR))

from backend_envs import build_install_plan, load_lock, select_backends, wrapper_text
from gpu_doctor import backend_probe


class BackendEnvironmentTests(unittest.TestCase):
    def test_trellis2_plan_pins_upstream_cuda_contract(self):
        lock = load_lock()
        plan = build_install_plan(
            "trellis2",
            lock["backends"]["trellis2"],
            manager="/usr/bin/conda",
            env_root=Path("/tmp/hayuya-envs"),
            model_root=Path("/tmp/hayuya-models"),
        )
        joined = "\n".join(" ".join(command) for command in plan.commands)
        self.assertIn("python=3.10", joined)
        self.assertIn("torch==2.6.0", joined)
        self.assertIn("cu124", joined)
        self.assertIn("--o-voxel", joined)
        self.assertIn("--flexgemm", joined)
        self.assertEqual(plan.cuda_family, "12.4")
        self.assertIn("CUDA_HOME=/usr/local/cuda-12.4", wrapper_text(plan))

    def test_wonder3d_keeps_legacy_isolated_stack(self):
        lock = load_lock()
        spec = lock["backends"]["wonder3d"]
        plan = build_install_plan(
            "wonder3d",
            spec,
            manager="conda",
            env_root=Path("/tmp/hayuya-envs"),
            model_root=Path("/tmp/hayuya-models"),
        )
        self.assertEqual(plan.python_version, "3.8")
        self.assertEqual(plan.torch_version, "1.13.1")
        self.assertEqual(plan.cuda_family, "11.7")
        direct_torch_installs = [
            command for command in plan.commands
            if any(part.startswith("torch==") for part in command)
        ]
        self.assertEqual(
            direct_torch_installs,
            [],
            "Wonder3D requirements.txt already pins its Torch/cu117 stack",
        )

    def test_support_selection_is_deduplicated(self):
        lock = load_lock()
        selected = select_backends(
            lock,
            repeated=["triposf"],
            csv="triposg,dinov2",
            include_support=True,
        )
        self.assertEqual(selected.count("dinov2"), 1)
        self.assertEqual(selected.count("triposf"), 1)
        self.assertIn("wonder3d", selected)

    def test_gpu_doctor_rejects_wrong_torch_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "triposg"
            (repo / ".git").mkdir(parents=True)
            python = root / "fake-python"
            python.write_text("#!/bin/sh\n", encoding="utf-8")

            entry = {
                "id": "triposg",
                "license": "MIT",
                "sha": "abc123",
                "min_vram_gb": 8,
            }
            env_spec = {
                "python": "3.10",
                "torch": {
                    "version": "2.4.1",
                    "cuda_family": "12.1",
                },
            }

            def fake_run_text(command, cwd=None):
                if command[:3] == ["git", "rev-parse", "HEAD"]:
                    return 0, "abc123", ""
                if command[-1:] == ["--version"]:
                    return 0, "Python 3.10.14", ""
                return 0, "", ""

            key = "HAYUYA_TRIPOSG_PYTHON"
            with mock.patch.dict(os.environ, {key: str(python)}):
                with mock.patch("gpu_doctor.run_text", side_effect=fake_run_text):
                    with mock.patch(
                        "gpu_doctor.python_cuda_probe",
                        return_value={
                            "torch": "2.3.0+cu121",
                            "torch_cuda": "12.1",
                            "cuda_available": True,
                        },
                    ):
                        result = backend_probe(entry, root, env_spec)

            self.assertFalse(result["torch_version_matches"])
            self.assertTrue(result["cuda_family_matches"])
            self.assertFalse(result["ready"])

    def test_gpu_doctor_accepts_matching_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "triposg"
            (repo / ".git").mkdir(parents=True)
            python = root / "fake-python"
            python.write_text("#!/bin/sh\n", encoding="utf-8")

            entry = {
                "id": "triposg",
                "license": "MIT",
                "sha": "abc123",
                "min_vram_gb": 8,
            }
            env_spec = {
                "python": "3.10",
                "torch": {
                    "version": "2.4.1",
                    "cuda_family": "12.1",
                },
            }

            def fake_run_text(command, cwd=None):
                if command[:3] == ["git", "rev-parse", "HEAD"]:
                    return 0, "abc123", ""
                if command[-1:] == ["--version"]:
                    return 0, "Python 3.10.14", ""
                return 0, "", ""

            key = "HAYUYA_TRIPOSG_PYTHON"
            with mock.patch.dict(os.environ, {key: str(python)}):
                with mock.patch("gpu_doctor.run_text", side_effect=fake_run_text):
                    with mock.patch(
                        "gpu_doctor.python_cuda_probe",
                        return_value={
                            "torch": "2.4.1+cu121",
                            "torch_cuda": "12.1",
                            "cuda_available": True,
                        },
                    ):
                        result = backend_probe(entry, root, env_spec)

            self.assertTrue(result["python_version_matches"])
            self.assertTrue(result["torch_version_matches"])
            self.assertTrue(result["cuda_family_matches"])
            self.assertTrue(result["ready"])


if __name__ == "__main__":
    unittest.main()
