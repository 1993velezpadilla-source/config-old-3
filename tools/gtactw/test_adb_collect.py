#!/usr/bin/env python3
import subprocess
import unittest
from unittest import mock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adb_collect


class AdbCollectTests(unittest.TestCase):
    def test_parse_pm_path_handles_base_and_splits(self):
        text = """package:/data/app/pkg/base.apk
package:/data/app/pkg/split_config.arm64_v8a.apk
package:/data/app/pkg/split_data_main.apk
noise
"""
        self.assertEqual(
            adb_collect.parse_pm_path(text),
            [
                "/data/app/pkg/base.apk",
                "/data/app/pkg/split_config.arm64_v8a.apk",
                "/data/app/pkg/split_data_main.apk",
            ],
        )

    def test_safe_local_names_are_stable_and_unique_by_index(self):
        self.assertEqual(
            adb_collect.safe_local_name(
                "/data/app/abc/base.apk",
                0,
            ),
            "00_base.apk",
        )
        self.assertEqual(
            adb_collect.safe_local_name(
                "/data/app/abc/split config.arm64-v8a.apk",
                1,
            ),
            "01_split_config.arm64-v8a.apk",
        )

    @mock.patch.object(adb_collect, "connected_devices")
    def test_choose_single_authorized_device(self, connected):
        connected.return_value = [
            {
                "serial": "ABC123",
                "state": "device",
                "metadata": {},
            }
        ]
        self.assertEqual(
            adb_collect.choose_serial("adb", None),
            "ABC123",
        )

    @mock.patch.object(adb_collect, "connected_devices")
    def test_choose_rejects_multiple_without_serial(self, connected):
        connected.return_value = [
            {"serial": "A", "state": "device", "metadata": {}},
            {"serial": "B", "state": "device", "metadata": {}},
        ]
        with self.assertRaises(RuntimeError):
            adb_collect.choose_serial("adb", None)

    @mock.patch.object(adb_collect, "connected_devices")
    def test_choose_explicit_serial(self, connected):
        connected.return_value = [
            {"serial": "A", "state": "device", "metadata": {}},
            {"serial": "B", "state": "device", "metadata": {}},
        ]
        self.assertEqual(
            adb_collect.choose_serial("adb", "B"),
            "B",
        )

    @mock.patch.object(adb_collect.subprocess, "run")
    def test_connected_devices_parser(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=["adb", "devices", "-l"],
            returncode=0,
            stdout=(
                "List of devices attached\n"
                "ABC123 device product:foo model:Pixel_Fold device:felix\n"
                "NOPE unauthorized usb:1-1\n"
            ),
            stderr="",
        )
        devices = adb_collect.connected_devices("adb")
        self.assertEqual(devices[0]["serial"], "ABC123")
        self.assertEqual(devices[0]["state"], "device")
        self.assertEqual(devices[0]["metadata"]["model"], "Pixel_Fold")
        self.assertEqual(devices[1]["state"], "unauthorized")


if __name__ == "__main__":
    unittest.main()
