from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.hayuya3d import texture_runtime, texture_superres


class TextureRuntimeTests(unittest.TestCase):
    def test_lock_pins_verified_linux_release(self):
        lock=texture_runtime.load_lock()
        entry=lock["runtimes"]["realesrgan-ncnn-vulkan"]
        asset=entry["assets"]["linux-x86_64"]
        self.assertEqual(entry["version"],"v0.2.5.0")
        self.assertEqual(
            entry["upstream_commit"],
            "685d429c81888252bdb10f56c7754baededc3823",
        )
        self.assertEqual(entry["license"],"BSD-3-Clause")
        self.assertEqual(
            asset["sha256"],
            "e5aa6eb131234b87c0c51f82b89390f5e3e642b7b70f2b9bbe95b6a285a40c96",
        )
        self.assertTrue(asset["url"].startswith("https://github.com/xinntao/"))

    def test_executable_path_finds_pinned_runtime_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            entry,asset=texture_runtime.runtime_spec()
            exe=(
                root/"realesrgan-ncnn-vulkan"/entry["version"]/
                asset["executable"]
            )
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b"stub")
            self.assertEqual(texture_runtime.executable_path(root),exe)

    def test_runtime_without_model_weights_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe=Path(tmp)/"realesrgan-ncnn-vulkan"
            exe.write_bytes(b"stub")
            ok,detail=texture_runtime.runtime_complete(exe)
            self.assertFalse(ok)
            self.assertIn("realesrgan-x4plus.param", detail or "")
            self.assertIn("realesrgan-x4plus.bin", detail or "")

    def test_runtime_with_required_model_weights_is_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe=Path(tmp)/"realesrgan-ncnn-vulkan"
            exe.write_bytes(b"stub")
            model_dir=exe.parent/"models"
            model_dir.mkdir()
            (model_dir/"realesrgan-x4plus.param").write_bytes(b"param")
            (model_dir/"realesrgan-x4plus.bin").write_bytes(b"bin")
            ok,detail=texture_runtime.runtime_complete(exe)
            self.assertTrue(ok)
            self.assertIsNone(detail)

    def test_ensure_realesrgan_uses_hash_pinned_installer_only_when_requested(self):
        fake=Path("/tmp/hayuya-pinned-realesrgan")
        with mock.patch(
            "tools.hayuya3d.texture_superres.find_realesrgan",
            return_value=None,
        ), mock.patch(
            "tools.hayuya3d.texture_runtime.install",
            return_value=fake,
        ) as install:
            self.assertIsNone(
                texture_superres.ensure_realesrgan(auto_install=False)
            )
            install.assert_not_called()
            self.assertEqual(
                texture_superres.ensure_realesrgan(auto_install=True),
                fake,
            )
            install.assert_called_once()


if __name__=="__main__":
    unittest.main()
