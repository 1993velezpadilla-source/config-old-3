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
        for name in ("iw3_vm_roll","iw3_vm_scale","iw3_vm_forward",
                     "iw3_vm_right","iw3_vm_up"):
            self.assertIn('{"'+name+'",',s)
            self.assertIn('Cvar_RegisterVariable(&'+name+');',s)
        self.assertIn('glRotatef(IWVM_Bounded(iw3_vm_roll.value',s)
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

    def test_legacy_cvar_defaults_are_identity(self):
        s=RENDER.read_text()
        for name in ("iw3_vm_roll","iw3_vm_forward","iw3_vm_right","iw3_vm_up"):
            self.assertIn('{"'+name+'", "0"}',s)
        self.assertIn('{"iw3_vm_scale", "1"}',s)

if __name__=="__main__":
    unittest.main()
