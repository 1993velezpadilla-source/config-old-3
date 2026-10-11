#!/usr/bin/env python3
"""CI-only: inject native Marmalade touches without am start / Activity pause."""
from pathlib import Path
import sys

assert len(sys.argv) == 2
p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
if "XZIEL_BROADCAST_NATIVE_TOUCH" in s:
    print("XZIEL_BROADCAST_NATIVE_TOUCH_ALREADY_PATCHED")
    raise SystemExit(0)
assert "XZIEL_DIRECT_NATIVE_TAP" in s, "apply existing native touch patch first"
anchor = "import android.content.Intent\n"
assert s.count(anchor) == 1, "unknown IsDeviceActivity imports"
s=s.replace(anchor,anchor+"""import android.content.BroadcastReceiver
import android.content.Context
import android.content.IntentFilter
""",1)
method_anchor = "    override fun onNewIntent(intent: Intent) {"
assert s.count(method_anchor)==1, "missing native touch source bridge"
receiver=r"""
    // XZIEL_BROADCAST_NATIVE_TOUCH: INTERNAL QA ONLY, never ship exported!
    // Starting Activity pauses/resumes Marmalade on EVERY press.
    // Dynamic receiver delivers down+up without Activity lifecycle events.
    private var m_XzielDiagnosticTouchReceiver: BroadcastReceiver? = null
    private fun xzielInstallNativeTouchReceiver() {
        val filter = IntentFilter("com.activision.boz.XZIEL_NATIVE_TOUCH")
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                if (intent?.action != "com.activision.boz.XZIEL_NATIVE_TOUCH") return
                val x = intent.getIntExtra("xzielX", 1140)
                val y = intent.getIntExtra("xzielY", 540)
                window.decorView.post {
                    try {
                        LoaderThread().onMotionEvent(0, 4, x, y)
                        window.decorView.postDelayed({
                            try {
                                LoaderThread().onMotionEvent(0, 5, x, y)
                                Log.i(TAG, "XZIEL_BROADCAST_NATIVE_TOUCH delivered x=$x y=$y no_activity_restart")
                            } catch (t: Throwable) {
                                Log.e(TAG, "XZIEL_BROADCAST_NATIVE_TOUCH UP_FAILED", t)
                            }
                        }, 160L)
                    } catch (t: Throwable) {
                        Log.e(TAG, "XZIEL_BROADCAST_NATIVE_TOUCH DOWN_FAILED", t)
                    }
                }
            }
        }
        if (Build.VERSION.SDK_INT >= 33) {
            registerReceiver(receiver, filter, Context.RECEIVER_EXPORTED)
        } else {
            @Suppress("DEPRECATION")
            registerReceiver(receiver, filter)
        }
        m_XzielDiagnosticTouchReceiver = receiver
        Log.i(TAG, "XZIEL_BROADCAST_NATIVE_TOUCH_REGISTERED")
    }

"""
s=s.replace(method_anchor,receiver+method_anchor,1)
create_anchor = "        m_Activity = this\n    }\n\n    override fun onStart()"
assert s.count(create_anchor)==1, "onCreate registration anchor missing"
s=s.replace(create_anchor,"        m_Activity = this\n        xzielInstallNativeTouchReceiver()\n    }\n\n    override fun onStart()",1)
destroy_anchor = "    override fun onDestroy() {\n        super.onDestroy()\n    }"
assert s.count(destroy_anchor)==1, "onDestroy cleanup anchor missing"
s=s.replace(destroy_anchor,"""    override fun onDestroy() {
        m_XzielDiagnosticTouchReceiver?.let {
            try { unregisterReceiver(it) } catch (_: Exception) {}
        }
        m_XzielDiagnosticTouchReceiver = null
        super.onDestroy()
    }""",1)
p.write_text(s,encoding="utf-8")
assert "XZIEL_BROADCAST_NATIVE_TOUCH_REGISTERED" in p.read_text()
assert "Context.RECEIVER_EXPORTED" in p.read_text()
assert "LoaderThread().onMotionEvent(0, 5, x, y)" in p.read_text()
print("XZIEL_BROADCAST_NATIVE_TOUCH_PATCH_GREEN")
