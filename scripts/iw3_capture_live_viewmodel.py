#!/usr/bin/env python3
"""Capture first in-game first-person frames *before* idle zombies kill player.

Do not capture after an arbitrary 70s delay: emulated NZ:P frequently
transitions to GAME OVER and Android Pixel Launcher ANR overlays by then.
Images are directly from adb screencap, never simulated/rendered artwork.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from PIL import Image
import struct
import subprocess
import time

PACKAGE="com.xziel.viriliw3"
ACTIVITY="org.libsdl.app.NZPActivity"
STAGE="files/nzp-runtime/.xziel-stage"


def adb(*args,timeout=15,check=True):
    return subprocess.run(["adb",*args],capture_output=True,
                          timeout=timeout,check=check)


def screenshot(path):
    data=adb("exec-out","screencap","-p",timeout=20).stdout
    if len(data)<10000 or data[:8]!=b"\x89PNG\r\n\x1a\n":
        raise ValueError("Expected actual emulator PNG screenshot")
    w,h=struct.unpack_from(">II",data,16)
    if not 640<=w<=8192 or not 360<=h<=4320:
        raise ValueError("Unexpected Android display resolution")
    path.write_bytes(data)
    print(f"ANDROID_LIVE_FRAME {path.name} {w}x{h} bytes={len(data)}",flush=True)


def capture(output:Path,timeout:int=90):
    output.mkdir(parents=True,exist_ok=True)
    adb("shell","am","start","-n",PACKAGE+"/"+ACTIVITY,
        "--ez","xziel_ci_hud_preview","true",timeout=25)
    ready=False
    for _ in range(timeout):
        result=adb("shell","run-as",PACKAGE,"cat",STAGE,
                   timeout=12,check=False)
        if b"FIRST_FRAME_OK" in result.stdout:
            ready=True
            break
        time.sleep(1)
    if not ready:
        raise RuntimeError("No original Vril 3D frame before timeout")
    # FIRST_FRAME_OK can precede Android's first SWAP_BUFFERS: a genuine
    # black 2400x1080 PNG has been observed even when GLES draw succeeded.
    # Do not claim a black screen as real gameplay evidence. Read pixels.
    first=output/"01-first-live-frame.png"
    for attempt in range(20):
        time.sleep(1)
        screenshot(first)
        with Image.open(first) as img:
            img=img.convert("RGB")
            img.thumbnail((128,72))
            palette={(r//12,g//12,b//12) for r,g,b in img.getdata()}
        if len(palette)>50:
            print("ANDROID_LIVE_FRAME_VERIFIED visible_palette_bins=",len(palette),
                  "frame_attempt=",attempt+1,flush=True)
            break
        print("ANDROID_LIVE_FRAME_RETRY blank buffer before SWAP_BUFFERS",
              "frame_attempt=",attempt+1,flush=True)
        first.unlink(missing_ok=True)
    else:
        raise RuntimeError("Actual Android 3D frame remained black/blank; no screenshot accepted")
    # User gameplay evidence: second distinct camera look while alive.
    adb("shell","input","swipe","1950","530","1670","535","250",timeout=12)
    time.sleep(1)
    screenshot(output/"02-live-look.png")
    return True


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--timeout",type=int,default=90)
    a=parser.parse_args()
    capture(a.out,a.timeout)
