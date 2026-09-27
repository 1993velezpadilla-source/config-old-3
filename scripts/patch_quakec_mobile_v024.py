#!/usr/bin/env python3
"""Xziel v0.24: allow normal weapon fire during the mobile slide.

The v0.21 slide correctly exits sprint and enters crouch, but the sprint-stop
viewmodel transition can still leave the weapon animation locked for a short
moment. Clear only that sprint-stop animation lock. Reload/swap/grenade timing
is intentionally left untouched, so slide cannot be used to cancel gameplay
cooldowns.

Applied after patch_quakec_mobile_v022.py.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_quakec_mobile_v024.py <quakec-root>")

root = Path(sys.argv[1])
weapon = root / "source" / "server" / "weapons" / "weapon_core.qc"
text = weapon.read_text(encoding="utf-8")

start = text.find("void() Xziel_MobileCrouchSlide =")
if start < 0:
    raise SystemExit("Could not find Xziel_MobileCrouchSlide")
end = text.find("\n};", start)
if end < 0:
    raise SystemExit("Could not find Xziel_MobileCrouchSlide end")
end += 3
chunk = text[start:end]

old = '''\tW_AimOut();
\tif (self.sprinting)
\t\tW_SprintStop();
\tself.sprintflag = false;
'''
new = '''\tW_AimOut();
\tif (self.sprinting)
\t\tW_SprintStop();

\t// Sprint-stop is only a presentation transition. The slide has its own
\t// first-person pose in Vril, so do not let that old transition block the
\t// first shot. Reload/swap/grenade delay fields are deliberately untouched.
\tself.new_anim_stop = false;
\tself.new_anim2_stop = false;
\tself.fire_delay = 0;
\tself.fire_delay2 = 0;

\tself.sprintflag = false;
'''
if "do not let that old transition block" not in chunk:
    if old not in chunk:
        raise SystemExit("Could not find slide sprint-stop block")
    chunk = chunk.replace(old, new, 1)
    text = text[:start] + chunk + text[end:]



# ---------------------------------------------------------------------------
# Reload while sprinting.
# Stock NZ:P's sprint transitions replace the active weapon animation and
# zero reload_delay/reload_delay2. On mobile that makes a movement action
# cancel an already-started reload. Preserve reload animation/timers while
# still allowing sprint locomotion.
# ---------------------------------------------------------------------------
def replace_function(src: str, signature: str, replacement: str) -> str:
    start = src.find(signature)
    if start < 0:
        raise SystemExit("Could not find function: " + signature)
    brace = src.find("{", start)
    if brace < 0:
        raise SystemExit("Could not find function body: " + signature)
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
        raise SystemExit("Could not find function end: " + signature)
    if end < len(src) and src[end] == ";":
        end += 1
    return src[:start] + replacement + src[end:]

sprint_stop = r'''void() W_SprintStop =
{
	if (self.isBuying || !self.sprinting)
		return;

	float xziel_reloading =
		self.reload_delay > time ||
		self.reload_delay2 > time;

	/* Reload owns the viewmodel until its ammo callback completes. Sprint
	   stop may change locomotion state, but must not replace that animation. */
	if (!xziel_reloading) {
		Weapon_PlayViewModelAnimation(ANIM_SPRINT_STOP, ReturnWeaponModel, 0);
		PAnim_Walk6();
	}

	self.zoom = 0;
	if (!xziel_reloading)
		self.tp_anim_time = 0;
	self.sprinting = 0;
	self.into_sprint = 0;

	/* Never clear reload timers here. They remain authoritative until the
	   reload callback loads the magazine. */
	self.fire_delay2 = self.fire_delay = 0;
	self.sprint_stop_time = time;
	self.sprint_duration = self.sprint_timer;
}'''

sprint_start = r'''void W_SprintStart () {
	if (self.speed_penalty_time > time || self.zoom != 0)
		return;

	self.sprint_start_time = time;

	if (self.sprint_rest_time > sprint_max_time)
		self.sprint_duration = 0.0;
	else
		self.sprint_duration -= self.sprint_rest_time;

	if (!self.sprintflag)
		return;

	float xziel_reloading =
		self.reload_delay > time ||
		self.reload_delay2 > time;

	if (self.fire_delay > time ||
		self.fire_delay2 > time ||
		(!xziel_reloading && self.new_anim_stop) ||
		(!xziel_reloading && self.new_anim2_stop) ||
		self.isBuying ||
		self.downed ||
		!(self.flags & FL_ONGROUND) ||
		self.sprint_delay > time) {
		return;
	}

	/* Sprint changes movement immediately, but an in-progress reload keeps
	   ownership of the first-person weapon animation and ammo callback. */
	if (!xziel_reloading)
		Weapon_PlayViewModelAnimation(ANIM_SPRINT_START, ContinueRun, 0);

	self.zoom = 3;
	self.sprint_delay = time + 1;
	self.sprinting = true;

	if (!xziel_reloading)
		self.fire_delay2 = self.fire_delay = 0;
}'''

text = replace_function(text, "void() W_SprintStop =", sprint_stop)
text = replace_function(text, "void W_SprintStart ()", sprint_start)

weapon.write_text(text, encoding="utf-8")
print("Applied Xziel v0.24 fire-during-slide + reload-while-sprinting behavior.")
