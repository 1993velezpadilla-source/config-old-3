#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "XZIEL_DIRECT_NATIVE_TAP"

INSERTION = r'''
    // XZIEL CI diagnostic: inject the exact native touch codes that
    // MultiTouch.onTouchEvent() normally forwards to LoaderThread.
    // This bypasses adb/input-device quirks while preserving the BOZ native
    // input path itself.
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)

        if (intent.getBooleanExtra("xzielDirectTap", false)) {
            val x = intent.getIntExtra("xzielX", 1140)
            val y = intent.getIntExtra("xzielY", 540)

            window.decorView.post {
                try {
                    LoaderThread().onMotionEvent(0, 4, x, y) // TOUCH_DOWN
                    window.decorView.postDelayed({
                        try {
                            LoaderThread().onMotionEvent(0, 5, x, y) // TOUCH_UP
                            Log.i(TAG, "XZIEL_DIRECT_NATIVE_TAP x=$x y=$y")
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

    anchor = "    override fun onDestroy() {"
    if anchor not in text:
        raise SystemExit("onDestroy anchor not found")

    text = text.replace(anchor, INSERTION + anchor, 1)
    p.write_text(text, encoding="utf-8")

    verify = p.read_text(encoding="utf-8")
    assert "override fun onNewIntent(intent: Intent)" in verify
    assert "LoaderThread().onMotionEvent(0, 4, x, y)" in verify
    assert "LoaderThread().onMotionEvent(0, 5, x, y)" in verify
    assert MARKER in verify
    print("XZIEL_DIRECT_NATIVE_TAP_PATCH_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
