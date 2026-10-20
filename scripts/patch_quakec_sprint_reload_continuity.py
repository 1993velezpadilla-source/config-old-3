#!/usr/bin/env python3
"""Gameplay-authoritative sprint/reload coexistence for NZ:P QuakeC.

Applied after the existing v0.24 mobile patch; retains weapon-specific reload
frames and magazine transfer events. The mobile sprint presentation may enter
or leave sprint during reload, but NEVER replaces the reload animation or zeros
its cooldown. This is not a client-only animation spoof.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_quakec_sprint_reload_continuity.py <quakec-root>")
path = Path(sys.argv[1]) / "source/server/weapons/weapon_core.qc"
src = path.read_text(encoding="utf-8")

def function(name: str) -> tuple[int, int, str]:
    candidates = (f"void() {name} =", f"void {name} ()")
    starts = [src.find(token) for token in candidates if token in src]
    if len(starts) != 1:
        raise RuntimeError(f"Missing or ambiguous QuakeC function {name}: {starts}")
    start = starts[0]
    brace = src.find("{", start)
    depth = 0
    end = -1
    for i in range(brace, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end < 0:
        raise RuntimeError("Unbalanced braces " + name)
    return start, end, src[start:end]

def patch_fn(name: str, old: str, new: str) -> None:
    global src
    start, end, body = function(name)
    if body.count(old) != 1:
        raise RuntimeError(f"{name}: expected one exact upstream code anchor, found {body.count(old)}")
    src = src[:start] + body.replace(old, new, 1) + src[end:]

patch_fn("W_Reload", "\tW_AimOut();\n\tW_SprintStop();",
         "\tW_AimOut();\n\t/* XZIEL_RELOAD_SPRINT_CONTINUITY: do not stop sprint when reloading.\n"
         "\t * The authoritative reload frames, ammo transfer and delay continue. */")

patch_fn("W_SprintStop",
    "\tWeapon_PlayViewModelAnimation(ANIM_SPRINT_STOP, ReturnWeaponModel, 0);",
    "\t/* Leave reloading viewmodels alone: sprint stop cannot overwrite them. */\n"
    "\tfloat xziel_reload_in_flight =\n"
    "\t\tself.reload_delay > time || self.reload_delay2 > time;\n"
    "\tif (!xziel_reload_in_flight)\n"
    "\t\tWeapon_PlayViewModelAnimation(ANIM_SPRINT_STOP, ReturnWeaponModel, 0);"
)
patch_fn("W_SprintStop",
    "\tself.reload_delay2 = self.fire_delay2 = self.reload_delay = self.fire_delay = 0;",
    "\tif (!xziel_reload_in_flight) {\n"
    "\t\tself.reload_delay2 = self.fire_delay2 = self.reload_delay = self.fire_delay = 0;\n"
    "\t}\n"
    "\t/* XZIEL_SPRINT_STOP_PRESERVES_RELOAD: never clear real reload clocks. */"
)
patch_fn("W_SprintStart",
    "\tif (self.fire_delay > time ||",
    "\t/* XZIEL_SPRINT_RELOAD_ALLOWED: preserve the entire weapon reload\n"
    "\t * while allowing physical sprint. No sprint animation is played. */\n"
    "\tif (self.reload_delay > time || self.reload_delay2 > time) {\n"
    "\t\tif (self.sprintflag && !self.isBuying && !self.downed &&\n"
    "\t\t    (self.flags & FL_ONGROUND)) {\n"
    "\t\t\tself.sprinting = true;\n"
    "\t\t\tself.zoom = 3;\n"
    "\t\t}\n"
    "\t\treturn;\n"
    "\t}\n"
    "\tif (self.fire_delay > time ||"
)
for marker in (
    "XZIEL_RELOAD_SPRINT_CONTINUITY",
    "XZIEL_SPRINT_STOP_PRESERVES_RELOAD",
    "XZIEL_SPRINT_RELOAD_ALLOWED",
):
    if src.count(marker) != 1:
        raise RuntimeError(f"Missing/duplicate sprint reload marker {marker}")
path.write_text(src, encoding="utf-8")
print("XZIEL_AUTHORITATIVE_RELOAD_WHILE_SPRINTING_GREEN")
