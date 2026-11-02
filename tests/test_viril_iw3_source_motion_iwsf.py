"""Source-only, synthetic checks for exact COD4-keyframe driven skin preview.

No proprietary CoD4 geometry, bone names or animation values in these tests.
"""
import math,struct,sys
from pathlib import Path
from unittest.mock import patch
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import iw3_xanim_to_iwsf as motion
from iw3_glb_to_iwsk import HEADER as SKIN_HEADER,BONE
from iw3_glb_to_iwvm import IDENT


def synth_skin():
    n=b"tag_weapon".ljust(64,b"\0")
    return SKIN_HEADER.pack(b"IWSK",1,1,1,0)+BONE.pack(n,-1,*IDENT,*IDENT)


def synth_source(has_match=True):
    return {
        "frames":3,"fps":30.,"looped":False,"root_delta":None,
        "bones":[{"name":"tag_weapon" if has_match else "other_unrelated_tag",
                  "rotation":{"kind":"full","raw_values":[[0,0,0],[13000,0,0]],
                              "frame_indices":[0,2],"flip_first":False},
                  "position":{"kind":"quantized_u8","frame_indices":[0,2],
                              "xyz":[[0.,0.,0.],[2.,0.,0.]]}}]
    }


class OriginalMotionSkinMatrixTest(unittest.TestCase):
    @patch.object(motion,"export_skin")
    @patch.object(motion,"decode")
    def test_exact_source_bone_frame_deltas_preserve_bind_pose(self,decoded,skin):
        decoded.return_value=synth_source()
        skin.return_value=synth_skin(),{}
        binary,meta=motion.pack_original_preview(Path("unused.glb"),Path("unused.xanim"))
        self.assertEqual(motion.FRAME_HEADER.unpack_from(binary),
                         (b"IWSF",1,3,1,30.))
        self.assertEqual(len(binary),motion.FRAME_HEADER.size+3*16*4)
        first=struct.unpack_from("<16f",binary,motion.FRAME_HEADER.size)
        last=struct.unpack_from("<16f",binary,motion.FRAME_HEADER.size+2*64)
        self.assertTrue(all(abs(v-IDENT[i])<1e-5 for i,v in enumerate(first)))
        self.assertGreater(max(abs(a-b) for a,b in zip(first,last)),.1)
        self.assertGreater(meta["joints_animated_from_original_keyframes"],0)
        self.assertFalse(meta["native_runtime_playback_verified"])

    @patch.object(motion,"export_skin")
    @patch.object(motion,"decode")
    def test_never_fabricate_motion_from_nonmatching_bones(self,decoded,skin):
        decoded.return_value=synth_source(False)
        skin.return_value=synth_skin(),{}
        with self.assertRaisesRegex(ValueError,"does not move any matching"):
            motion.pack_original_preview(Path("unused.glb"),Path("unused.xanim"))

    def test_original_quat2_orientation_stays_finite(self):
        bone={"rotation":{"kind":"half","raw_values":[[0],[9000]],
                          "frame_indices":[0,2],"flip_first":False},
              "position":{"kind":"none","frame_indices":[],"xyz":[]}}
        from iw3_xanim_pose_sample import original_quantized_quaternion
        first=original_quantized_quaternion(bone["rotation"],0,3)
        m=motion.local_delta(bone,1.,3,first)
        self.assertEqual(len(m),16)
        self.assertTrue(all(math.isfinite(x) for x in m))
        self.assertNotEqual(m,motion.ORIGINAL_TO_QUAKE)

if __name__=="__main__":
    unittest.main()
