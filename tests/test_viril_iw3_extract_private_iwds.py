"""Safe unit tests for matching COD4 IWD image lookup, no game asset bytes."""
import sys, tempfile, zipfile
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from iw3_extract_private_iwds import extract_from_iwd

class OriginalIWDExtractTest(unittest.TestCase):
    def test_only_original_requested_iwi_extracted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            sample=root/"test.iwd"
            with zipfile.ZipFile(sample,"w") as z:
                z.writestr("images/usp_color.iwi",b"IWi"+b"S"*50)
                z.writestr("images/other.iwi",b"IWi"+b"B"*40)
                z.writestr("readme.txt",b"not supposed to extract")
            out=root/"private"
            found=extract_from_iwd(sample,{"images/usp_color.iwi"},out)
            self.assertEqual(found,{"images/usp_color.iwi"})
            self.assertEqual((out/"images/usp_color.iwi").read_bytes(),b"IWi"+b"S"*50)
            self.assertFalse((out/"images/other.iwi").exists())
            self.assertFalse((out/"readme.txt").exists())
    def test_missing_iwi_is_not_faked(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"missing.iwd"
            with zipfile.ZipFile(p,"w") as z:z.writestr("images/missing.iwi",b"IWi"+b"X"*60)
            self.assertEqual(extract_from_iwd(p,{"images/usp.iwi"},Path(tmp)/"out"),set())
    def test_reject_large_original_iwi_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"large.iwd"
            with zipfile.ZipFile(p,"w") as z:z.writestr("images/large.iwi",b"IWi"+b"X"*65)
            # A harmless synthetic oversized zipinfo, no huge file allocation.
            import iw3_extract_private_iwds
            old=iw3_extract_private_iwds.MAX_IMAGE_BYTES
            try:
                iw3_extract_private_iwds.MAX_IMAGE_BYTES=50
                with self.assertRaisesRegex(ValueError,"Invalid source COD4 IWI size"):
                    extract_from_iwd(p,{"images/large.iwi"},Path(tmp)/"out")
            finally:
                iw3_extract_private_iwds.MAX_IMAGE_BYTES=old

if __name__=="__main__":unittest.main()
