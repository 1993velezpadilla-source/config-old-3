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


def dismiss_os_fullscreen_dialog(image:Image.Image):
    """Clear Android's immersive-mode 'Viewing full screen / Got it' once.

    A prior original-COD4 screenshot was 100% covered by this operating-
    system popup even though GLES gun/texture logging passed. Detect the
    dialog's distinctive blue confirmation button; never blindly tap GUI.
    """
    w,h=image.size
    if w<900 or h<600:
        return False
    r,g,b=image.getpixel((int(w*.71),int(h*.47)))
    center=image.getpixel((int(w*.5),int(h*.4)))
    button_is_blue=(48<=r<=120 and 60<=g<=145 and 110<=b<=195 and b>g*1.25)
    card_is_pale=min(center)>215
    if not (button_is_blue and card_is_pale):
        return False
    print("ANDROID_OS_OVERLAY: immersive first-launch confirmation; dismiss",flush=True)
    adb("shell","input","tap",str(int(w*.71)),str(int(h*.47)))
    time.sleep(1)
    # This Android emulator also presents an app-not-responding 'Wait'
    # dialog behind the fullscreen tip under software graphics load.
    # A secondary tap is only attempted in this known two-dialog state.
    adb("shell","input","tap",str(int(w*.29)),str(int(h*.63)))
    time.sleep(1)
    return True


def dismiss_os_anr_dialog(image:Image.Image):
    """Detect the *different* Android Pixel Launcher 'Wait' dialog.

    This is often revealed only AFTER the fullscreen confirmation is
    dismissed. Older code tapped 'Wait' before it was interactable and
    accepted its high-color screenshot as gameplay. Never do that.
    """
    w,h=image.size
    if w<900 or h<600: return False
    center=image.getpixel((int(w*.50),int(h*.45)))
    edge=image.getpixel((int(w*.10),int(h*.50)))
    low=image.getpixel((int(w*.50),int(h*.85)))
    right=image.getpixel((int(w*.70),int(h*.45)))
    # Pixel launcher ANR: broad pale card over a very dark rendered map.
    is_card=(min(center)>215 and min(right)>215 and
             max(edge)<90 and max(low)<90)
    if not is_card: return False
    print("ANDROID_OS_OVERLAY: Pixel Launcher ANR Wait; dismiss",flush=True)
    adb("shell","input","tap",str(int(w*.32)),str(int(h*.61)))
    time.sleep(2)
    return True


def capture(output:Path,timeout:int=90,tap_reload:bool=False):
    output.mkdir(parents=True,exist_ok=True)
    adb("shell","settings","put","secure","immersive_mode_confirmations",
        "confirmed",timeout=12,check=False)
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
            if dismiss_os_fullscreen_dialog(img) or dismiss_os_anr_dialog(img):
                first.unlink(missing_ok=True)
                continue
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
    if tap_reload:
        # v0.26 default normalized reload HUD center. Proof must come from
        # native input and vertex deformation logs, not just this screenshot.
        with Image.open(first) as img:
            w,h=img.size
        tx,ty=int(w*.805),int(h*.785)
        fx,fy=int(w*.885),int(h*.585)
        # Negative control: 8/32 full magazine MUST NOT start COD4 motion.
        print(f"ANDROID_FULLMAG_RELOAD_PROBE x={tx} y={ty}",flush=True)
        adb("shell","input","tap",str(tx),str(ty),timeout=12)
        time.sleep(1.25) # native ack timeout, before any firing
        screenshot(output/"03-fullmag-reload-rejected.png")
        # Real touchscreen fire, 8/32 -> 7/32 before an accepted reload.
        print(f"ANDROID_FIRE_TOUCH x={fx} y={fy}",flush=True)
        adb("shell","input","tap",str(fx),str(fy),timeout=12)
        time.sleep(.8) # Let the native gun-fire pose return to idle.
        screenshot(output/"04-after-fire.png")
        print(f"ANDROID_RELOAD_TOUCH x={tx} y={ty} display={w}x{h}",flush=True)
        adb("shell","input","tap",str(tx),str(ty),timeout=12)
        time.sleep(.45)
        screenshot(output/"05-real-reload-source-moving.png")
        time.sleep(1.55)
        screenshot(output/"06-real-reload-finished.png")
    return True


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--timeout",type=int,default=90)
    parser.add_argument("--tap-reload",action="store_true")
    a=parser.parse_args()
    capture(a.out,a.timeout,a.tap_reload)
