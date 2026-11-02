#!/usr/bin/env python3
"""Ensure Android data installer refreshes after a converted-gun update."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from iw3_private_weapon_pack import prepare
from test_viril_iw3_glb_converter import example_glb


class IW3PrivateAssetInstallTests(unittest.TestCase):
    def test_android_asset_version_changes_with_private_model(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            glb=root/"models"
            glb.mkdir()
            (glb/"viewmodel_usp_lod0.glb").write_bytes(example_glb())
            mapping=root/"mapping.json"
            mapping.write_text(json.dumps([{
                "vril_viewmodel":"models/weapons/m1911/v_colt.mdl",
                "iw3_glb":"viewmodel_usp_lod0.glb",
                "scale":1
            }]))
            package=root/"nzp-data.zip"
            with zipfile.ZipFile(package,"w") as z:
                z.writestr("nzp/progs.dat",b"original")
            version=package.with_suffix(".version")
            original_hash=hashlib.sha256(package.read_bytes()).hexdigest()
            version.write_text(original_hash+"\n")
            dry=prepare(package,glb,mapping,dry_run=True)
            self.assertEqual(len(dry),1)
            self.assertEqual(original_hash,version.read_text().strip())
            report=prepare(package,glb,mapping)
            self.assertEqual(len(report),1)
            with zipfile.ZipFile(package) as z:
                self.assertEqual(z.read("nzp/progs.dat"),b"original")
                converted=z.read("nzp/models/iw3/v_colt.iwvm")
                self.assertEqual(converted[:4],b"IWVM")
            self.assertEqual(report[0]["archive_entry"],
                             "nzp/models/iw3/v_colt.iwvm")
            self.assertNotIn("models/iw3/v_colt.iwvm",
                             zipfile.ZipFile(package).namelist())
            sha=hashlib.sha256(package.read_bytes()).hexdigest()
            self.assertNotEqual(sha,original_hash)
            self.assertEqual(sha,version.read_text().strip())

if __name__=="__main__":
    unittest.main()
