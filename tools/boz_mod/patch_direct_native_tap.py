#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "XZIEL_DIRECT_NATIVE_TAP"

INSERTION = r'''
    // XZIEL CI diagnostic: synthesize the same Android MotionEvent pair a
    // physical finger would generate. Route it through Activity dispatch,
    // LoaderView, LoaderThread and MultiTouch before it reaches native BOZ.
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)

        // Diagnostic native lane: when the normal Android dispatch returned
        // true but the BOZ map selector did not change, invoke the same
        // Marmalade JNI onMotionEvent method used by MultiTouch directly.
        // Native event ids 4=down, 5=up are from the upstream source.
        if (intent.getBooleanExtra("xzielNativeTap", false)) {
            val nx = intent.getIntExtra("xzielX", 1140)
            val ny = intent.getIntExtra("xzielY", 540)
            window.decorView.post {
                try {
                    val nativeThread = LoaderThread()
                    nativeThread.onMotionEvent(0, 4, nx, ny)
                    window.decorView.postDelayed({
                        try {
                            nativeThread.onMotionEvent(0, 5, nx, ny)
                            Log.i(TAG, "XZIEL_DIRECT_NATIVE_TAP JNI_ROUTE x=$nx y=$ny down=4 up=5")
                        } catch (t: Throwable) {
                            Log.e(TAG, "XZIEL_DIRECT_NATIVE_TAP JNI_UP_FAILED", t)
                        }
                    }, 140L)
                } catch (t: Throwable) {
                    Log.e(TAG, "XZIEL_DIRECT_NATIVE_TAP JNI_DOWN_FAILED", t)
                }
            }
        }
        if (intent.getBooleanExtra("xzielDirectTap", false)) {
            val x = intent.getIntExtra("xzielX", 1140).toFloat()
            val y = intent.getIntExtra("xzielY", 540).toFloat()

            window.decorView.post {
                try {
                    val downTime = SystemClock.uptimeMillis()
                    val down = MotionEvent.obtain(
                        downTime,
                        downTime,
                        MotionEvent.ACTION_DOWN,
                        x,
                        y,
                        0
                    )
                    down.source = InputDevice.SOURCE_TOUCHSCREEN
                    val downHandled = dispatchTouchEvent(down)
                    down.recycle()

                    window.decorView.postDelayed({
                        try {
                            val eventTime = SystemClock.uptimeMillis()
                            val up = MotionEvent.obtain(
                                downTime,
                                eventTime,
                                MotionEvent.ACTION_UP,
                                x,
                                y,
                                0
                            )
                            up.source = InputDevice.SOURCE_TOUCHSCREEN
                            val upHandled = dispatchTouchEvent(up)
                            up.recycle()
                            Log.i(
                                TAG,
                                "XZIEL_DIRECT_NATIVE_TAP realMotion x=$x y=$y " +
                                    "downHandled=$downHandled upHandled=$upHandled"
                            )
                        } catch (t: Throwable) {
                            Log.e(TAG, "XZIEL_DIRECT_NATIVE_TAP UP failed", t)
                        }
                    }, 120L)
                } catch (t: Throwable) {
                    Log.e(TAG, "XZIEL_DIRECT_NATIVE_TAP DOWN failed", t)
                }
            }
        }
    }

'''

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    args = ap.parse_args()

    p = args.source
    text = p.read_text(encoding="utf-8")
    if MARKER in text:
        print("XZIEL_DIRECT_NATIVE_TAP_ALREADY_PATCHED")
        return 0

    import_anchor = "import android.view.KeyEvent\n"
    if import_anchor not in text:
        raise SystemExit("KeyEvent import anchor not found")
    text = text.replace(
        import_anchor,
        import_anchor
        + "import android.view.InputDevice\n"
        + "import android.view.MotionEvent\n"
        + "import android.os.SystemClock\n",
        1,
    )

    anchor = "    override fun onDestroy() {"
    if anchor not in text:
        raise SystemExit("onDestroy anchor not found")

    text = text.replace(anchor, INSERTION + anchor, 1)
    p.write_text(text, encoding="utf-8")

    verify = p.read_text(encoding="utf-8")
    assert "override fun onNewIntent(intent: Intent)" in verify
    assert "MotionEvent.ACTION_DOWN" in verify
    assert "MotionEvent.ACTION_UP" in verify
    assert "InputDevice.SOURCE_TOUCHSCREEN" in verify
    assert "dispatchTouchEvent(down)" in verify
    assert "dispatchTouchEvent(up)" in verify
    assert "nativeThread.onMotionEvent(0, 4, nx, ny)" in verify
    assert "nativeThread.onMotionEvent(0, 5, nx, ny)" in verify
    assert MARKER in verify
    print("XZIEL_DIRECT_NATIVE_TAP_PATCH_OK")
    print("XZIEL_REAL_MOTION_EVENT_ROUTE_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
