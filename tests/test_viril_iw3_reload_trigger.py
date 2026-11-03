"""Source gates for authentic original CoD4 XAnim one-shot on real reload.

No CoD4 proprietary content in tests. Android CI must additionally prove
that a real HUD touch causes source-bone/vertex motion, not just a loaded clip.
"""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
RENDER=(ROOT/"android/jni/src/gl_iw3_weapon_mesh.c").read_text()
PATCH=(ROOT/"scripts/patch_viril_iw3_weapon_pose.py").read_text()
CAPTURE=(ROOT/"scripts/iw3_capture_live_viewmodel.py").read_text()
WORKFLOW=(ROOT/".github/workflows/viril-iw3-private-cod4-android.yml").read_text()

class OriginalOneShotReloadTests(unittest.TestCase):
    def test_native_touch_keyboard_input_edge(self):
        self.assertIn('void IW3_WeaponMesh_NotifyReload(void)',RENDER)
        self.assertIn('IW3_ORIGINAL_XANIM_RELOAD_INPUT',RENDER)
        self.assertIn('int was_down = (in_reload.state & 1);',PATCH)
        self.assertIn('KeyDown(&in_reload);',PATCH)
        self.assertIn('IW3_WeaponMesh_NotifyReload();',PATCH)

    def test_play_once_and_restore_full_rest_mesh(self):
        self.assertIn('iwsk_reload_active=0;',RENDER)
        self.assertIn('iwsk_reload_pending=0;',RENDER)
        self.assertIn('clock >= (float)iwsk_frame_count',RENDER)
        self.assertIn('clock=((float)cl.time-iwsk_reload_started_at)*rate;',RENDER)
        self.assertIn('IW3_ORIGINAL_XANIM_RELOAD_COMPLETE restored=bind_pose loop=0',RENDER)
        self.assertNotIn('fmodf(fabsf(clock)',RENDER)

    def test_ci_requires_real_touch_and_actual_deformed_vertices(self):
        self.assertIn('ANDROID_RELOAD_TOUCH',CAPTURE)
        self.assertIn('adb("shell","input","tap",str(tx),str(ty)',CAPTURE)
        self.assertIn('--tap-reload',WORKFLOW)
        self.assertIn('IW3_ORIGINAL_XANIM_RELOAD_TRIGGERED frames=40',WORKFLOW)
        self.assertIn('IW3_ORIGINAL_XANIM_SKIN_DEFORMED frame=',WORKFLOW)
        self.assertNotIn('"reloadEmptyAnim","fireAnim"',WORKFLOW)

if __name__=="__main__":
    unittest.main()
