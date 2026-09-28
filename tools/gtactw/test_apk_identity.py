#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apk_identity


GOOD_BADGING = """package: name='com.rockstargames.gtactw' versionCode='4277603' versionName='4.4.243'
sdkVersion:'28'
targetSdkVersion:'35'
application-label:'GTA: Chinatown Wars'
native-code: 'arm64-v8a' 'x86_64'
"""

BAD_BADGING = """package: name='com.example.wrong' versionCode='1' versionName='1.0'
sdkVersion:'21'
native-code: 'armeabi-v7a'
"""


class ApkIdentityTests(unittest.TestCase):
    def reference(self):
        return {
            "package": "com.rockstargames.gtactw",
            "reference_build": {
                "version_name": "4.4.243",
                "version_code": 4277603,
            },
            "android_mod_target": {
                "preferred_abi": "arm64-v8a",
            },
        }

    def test_parse_good_badging(self):
        identity = apk_identity.parse_badging(GOOD_BADGING)
        self.assertEqual(identity["package"], "com.rockstargames.gtactw")
        self.assertEqual(identity["version_code"], 4277603)
        self.assertEqual(identity["version_name"], "4.4.243")
        self.assertEqual(identity["min_sdk"], "28")
        self.assertEqual(identity["target_sdk"], "35")
        self.assertEqual(identity["native_code"], ["arm64-v8a", "x86_64"])

    def test_reference_match(self):
        identity = apk_identity.parse_badging(GOOD_BADGING)
        report = apk_identity.validate_reference(identity, self.reference())
        self.assertTrue(report["ok"])
        self.assertTrue(all(report["checks"].values()))

    def test_reference_mismatch(self):
        identity = apk_identity.parse_badging(BAD_BADGING)
        report = apk_identity.validate_reference(identity, self.reference())
        self.assertFalse(report["ok"])
        self.assertFalse(report["checks"]["package"])
        self.assertFalse(report["checks"]["version_code"])
        self.assertFalse(report["checks"]["arm64"])

    def test_badging_requires_identity_line(self):
        with self.assertRaises(ValueError):
            apk_identity.parse_badging("sdkVersion:'28'\n")


if __name__ == "__main__":
    unittest.main()
