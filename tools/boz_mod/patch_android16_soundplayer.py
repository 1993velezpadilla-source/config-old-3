#!/usr/bin/env python3
"""Prevent original BOZ/Marmalade JNI abort when Android 16 cannot init AudioTrack.

Source: eugene373/COD-BOZ-Partially-Decompiled pinned by XChurch CI.
A failed AudioTrack setup left m_Track non-null and uninitialized. start()
called play() anyway, raising IllegalStateException. The native runOnOSTick
did not clear that pending Java exception, so CheckJNI SIGABRTed the app.
No game/map/resource file is changed.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_android16_soundplayer.py SoundPlayer.kt")
p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
if "XZIEL_ANDROID16_AUDIO_GUARD" in s:
    print("XZIEL_ANDROID16_AUDIO_ALREADY_GUARDED")
    raise SystemExit(0)

old_init = """        if (m_Track!!.state != 1) {
            trace("AudioTrack not initialized")
            return 0
        }"""
new_init = """        // XZIEL_ANDROID16_AUDIO_GUARD: never retain unusable AudioTrack.
        if (m_Track?.state != AudioTrack.STATE_INITIALIZED) {
            trace("AudioTrack not initialized; releasing safely")
            try { m_Track?.release() } catch (_: IllegalStateException) {}
            m_Track = null
            m_SampleData = null
            m_NeedsPrime = false
            return 0
        }"""
assert s.count(old_init) == 1, "AudioTrack init source changed"
s = s.replace(old_init, new_init, 1)

old_start = """    fun start() {
        if (m_Track == null) {
            init(m_Volume, m_Stereo, m_SampleRate)
        }
        trace("starting sound")
        m_Track!!.play()
        if (m_NeedsPrime) {
            m_NeedsPrime = false
            writeSamples(m_Period * 2 * 2)
        }
    }"""
new_start = """    @Synchronized
    fun start() {
        // Never let an invalid AudioTrack produce a pending JNI exception.
        // Marmalade native runOnOSTickNative would otherwise abort on Android 16.
        if (m_Track?.state != AudioTrack.STATE_INITIALIZED) {
            try { m_Track?.release() } catch (_: IllegalStateException) {}
            m_Track = null
            if (init(m_Volume, m_Stereo, m_SampleRate) == 0) {
                trace("XZIEL_ANDROID16_AUDIO_GUARD: sound unavailable; skip play, game continues")
                return
            }
        }
        val track = m_Track ?: return
        if (track.state != AudioTrack.STATE_INITIALIZED) {
            trace("XZIEL_ANDROID16_AUDIO_GUARD: track uninitialized after init")
            return
        }
        trace("starting sound")
        try {
            track.play()
        } catch (e: IllegalStateException) {
            trace("XZIEL_ANDROID16_AUDIO_GUARD: suppressed bad AudioTrack.play: $e")
            try { track.release() } catch (_: IllegalStateException) {}
            m_Track = null
            m_NeedsPrime = false
            return
        }
        if (m_NeedsPrime) {
            m_NeedsPrime = false
            writeSamples(m_Period * 2 * 2)
        }
    }"""
assert s.count(old_start) == 1, "SoundPlayer.start source changed"
s = s.replace(old_start, new_start, 1)
assert "m_Track!!.play()" not in s
assert "XZIEL_ANDROID16_AUDIO_GUARD" in s
p.write_text(s, encoding="utf-8")
print("XZIEL_ANDROID16_AUDIO_GUARD_PATCH_OK")
