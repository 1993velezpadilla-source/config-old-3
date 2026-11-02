import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from iw3_xanim_pose_sample import original_quantized_quaternion,source_animation_pose,original_translation


class COD4SourceAnimationFrameTest(unittest.TestCase):
    def anim(self,loop=False):
        return {
            "frames":3,"looped":loop,"fps":30,"root_delta":None,
            "bones":[{"name":"tag_weapon",
                "rotation":{"kind":"full","frame_indices":[0,2],
                            "raw_values":[[0,0,0],[16000,0,0]],"flip_first":False},
                "position":{"kind":"quantized_u8","frame_indices":[0,2],
                            "xyz":[[0.,0.,0.],[2.,0.,0.]]},
            }]
        }

    def test_real_quaternion_decode_and_smooth_frame_interpolation(self):
        first=source_animation_pose(self.anim(),0)["bones"][0]
        mid=source_animation_pose(self.anim(),1)["bones"][0]
        end=source_animation_pose(self.anim(),2)["bones"][0]
        self.assertEqual(first["source_quaternion"][0],"quat4")
        self.assertEqual(first["source_translation"],(0.,0.,0.))
        self.assertEqual(mid["source_translation"],(1.,0.,0.))
        self.assertEqual(end["source_translation"],(2.,0.,0.))
        self.assertGreater(mid["source_quaternion"][1][0],0.)
        self.assertLess(mid["source_quaternion"][1][0],end["source_quaternion"][1][0])
        self.assertFalse(source_animation_pose(self.anim(),1)["original_animation_playing_in_vril"])

    def test_two_component_quat_is_not_fake_full_rotation(self):
        q={"kind":"half","frame_indices":[],"raw_values":[[0]],"flip_first":False}
        kind,val=original_quantized_quaternion(q,0,4)
        self.assertEqual(kind,"quat2")
        self.assertEqual(len(val),2)
        self.assertAlmostEqual(val[1],1.,places=3)

    def test_real_looping_and_clamping(self):
        end=source_animation_pose(self.anim(),200)["original_frame"]
        loop=source_animation_pose(self.anim(True),4)["original_frame"]
        self.assertEqual(end,2)
        self.assertEqual(loop,1)

    def test_corrupted_frame_index_rejected(self):
        t={"kind":"quantized_u16","frame_indices":[2,1],"xyz":[[0,0,0],[1,0,0]]}
        with self.assertRaises(ValueError):
            original_translation(t,1,4)

if __name__=="__main__":
    unittest.main()
