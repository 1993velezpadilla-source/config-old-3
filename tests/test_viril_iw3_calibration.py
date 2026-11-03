"""Ensure experimental first-person real-IW3 calibration is explicit and bounded.

This source-level gate complements native arm64 Android compilation. No
fake PNG/3D mesh is installed in any user release by these tests.
"""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
RENDER=ROOT/"android/jni/src/gl_iw3_weapon_mesh.c"
PATCH=ROOT/"scripts/patch_viril_iw3_weapon_pose.py"


class OriginalWeaponCalibrationTest(unittest.TestCase):
    def test_user_adjustable_pose_without_altering_nzp_mdl(self):
        s=RENDER.read_text()
        for name in ("iw3_vm_roll","iw3_vm_yaw","iw3_vm_scale","iw3_vm_forward",
                     "iw3_vm_right","iw3_vm_up"):
            self.assertIn('{"'+name+'",',s)
            self.assertIn('Cvar_RegisterVariable(&'+name+');',s)
        self.assertIn('glRotatef(IWVM_Bounded(iw3_vm_yaw.value',s)
        self.assertIn('glRotatef(IWVM_Bounded(iw3_vm_roll.value',s)
        self.assertIn('IW3_VM_CALIBRATION',s)
        # Yaw turns the authentic screenshot's -Y barrel axis into Quake +X.
        self.assertIn('0.f, 0.f, 1.f);',s)
        self.assertLess(s.index('glRotatef(IWVM_Bounded(iw3_vm_yaw.value'),
                        s.index('glRotatef(IWVM_Bounded(iw3_vm_roll.value'))
        self.assertIn('glScalef(sc, sc, sc);',s)
        self.assertIn('glTranslatef(',s)
        self.assertIn('if (!iwvm_mesh.vertex_count)',s)
        self.assertIn('return 0;',s)
        self.assertIn('IW3_MESH_BOUNDS',s)

    def test_generator_patches_vril_only(self):
        s=PATCH.read_text()
        self.assertIn('build/deps/vril/source/platform/sdl/gl',s)
        self.assertIn('IW3_WeaponMesh_RegisterCvars();',s)
        self.assertIn('IW3_WeaponMesh_Draw(currententity)',s)
        self.assertIn('R_DrawAliasModel (currententity)',s)
        self.assertNotIn('feature/viril-iw3-v026',s)

    def test_original_usp_android_capture_calibration_is_reversible(self):
        """Source photo showed a side-on, screen-filling original USP.

        This tuning only affects optional converted GLBs, NOT stable NZ:P MDL.
        It is not a claim of official COD4 offsets or visual QA success.
        """
        s=RENDER.read_text()
        expected={"iw3_vm_roll":"0","iw3_vm_yaw":"90",
                  "iw3_vm_scale":"0.65","iw3_vm_forward":"12",
                  "iw3_vm_right":"3","iw3_vm_up":"-2"}
        for name,value in expected.items():
            self.assertIn('{"'+name+'", "'+value+'"}',s)
        self.assertIn('if (!iwvm_mesh.vertex_count)',s)
        self.assertIn('return 0;',s)
        self.assertIn('IW3_WeaponMesh_Draw(entity_t *view)',s)
        # Screenshots showed the barrel in Quake local -Y. A +90 Z yaw
        # maps it to +X (looking forward) without changing source vertices.
        import math
        yaw=math.radians(float(expected["iw3_vm_yaw"]))
        source_barrel=(0.,-1.)
        new_x=math.cos(yaw)*source_barrel[0]-math.sin(yaw)*source_barrel[1]
        new_y=math.sin(yaw)*source_barrel[0]+math.cos(yaw)*source_barrel[1]
        self.assertAlmostEqual(new_x,1.,places=5)
        self.assertAlmostEqual(new_y,0.,places=5)

if __name__=="__main__":
    unittest.main()
