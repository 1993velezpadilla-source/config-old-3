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

GOOD_CERTS = """Signer #1 certificate DN: CN=War Drum Studios
Signer #1 certificate SHA-256 digest: e8:c7:62:84:d4:d6:52:f1:88:15:25:85:3c:e0:aa:9f:e8:2b:89:e2:76:f6:20:4f:1a:7a:53:ae:f6:7f:ce:19
Signer #1 certificate SHA-1 digest: 30:83:fe:16:8b:ed:e4:4d:52:02:b9:04:47:cd:47:a4:9a:7e:22:8d
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


    def reference_with_cert(self):
        ref = self.reference()
        ref["reference_build"]["signing_certificate"] = {
            "sha1": "3083fe168bede44d5202b90447cd47a49a7e228d",
            "sha256": "e8c76284d4d652f1881525853ce0aa9fe82b89e276f6204f1a7a53aef67fce19",
        }
        ref["verification"] = {
            "require_signing_certificate_match": True,
        }
        return ref

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


    def test_parse_certificate_digests(self):
        cert = apk_identity.parse_apksigner_certs(GOOD_CERTS)
        self.assertEqual(
            cert["sha1"],
            "3083fe168bede44d5202b90447cd47a49a7e228d",
        )
        self.assertEqual(
            cert["sha256"],
            "e8c76284d4d652f1881525853ce0aa9fe82b89e276f6204f1a7a53aef67fce19",
        )

    def test_reference_certificate_match(self):
        identity = apk_identity.parse_badging(GOOD_BADGING)
        cert = apk_identity.parse_apksigner_certs(GOOD_CERTS)
        report = apk_identity.validate_reference(
            identity,
            self.reference_with_cert(),
            cert,
        )
        self.assertTrue(report["ok"])
        self.assertTrue(report["checks"]["signing_certificate"])

    def test_reference_certificate_required(self):
        identity = apk_identity.parse_badging(GOOD_BADGING)
        report = apk_identity.validate_reference(
            identity,
            self.reference_with_cert(),
            None,
        )
        self.assertFalse(report["ok"])
        self.assertFalse(report["checks"]["signing_certificate"])

    def test_badging_requires_identity_line(self):
        with self.assertRaises(ValueError):
            apk_identity.parse_badging("sdkVersion:'28'\n")


if __name__ == "__main__":
    unittest.main()
