#!/usr/bin/env python3
"""Modern jump input/arc for Xziel's NZ:P QuakeC gameplay."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_quakec_modern_movement.py <quakec-root>")

root = Path(sys.argv[1])

def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"missing anchor: {label}")
    return text.replace(old, new, 1)

defs = root / "source/server/defs/custom.qc"
text = defs.read_text(encoding="utf-8")
anchor = ".vector new_ofs;\n"
fields = r'''.float xziel_jump_buffer_until;
.float xziel_last_grounded_time;
'''
if "xziel_jump_buffer_until" not in text:
    text = replace_once(text, anchor, anchor + fields, "player movement fields")
defs.write_text(text, encoding="utf-8")

player = root / "source/server/player/player_core.qc"
text = player.read_text(encoding="utf-8")

old_jump = r'''void() PlayerJump =
{
	if ((self.map_control_flags & PLAYER_CONTROL_FROZEN) || !(self.flags & FL_ONGROUND)
	    || !(self.flags & FL_JUMPRELEASED)
		|| self.downed 
		|| self.dive ) {
		return;
	}
			
	self.flags = self.flags - (self.flags & FL_JUMPRELEASED);

	if (self.button2)
		self.button2 = 0;
	
	self.oldz = self.origin_z;

	self.velocity_z = 230;
}'''

new_jump = r'''void() PlayerJump =
{
	float modern_movement = cvar("xziel_modern_movement") >= 0.5;
	float can_leave_ground = self.flags & FL_ONGROUND;

	/* Small coyote window makes mobile/controller jumping responsive without
	   changing collision or allowing double-jumps. */
	if (!can_leave_ground && modern_movement &&
		time <= self.xziel_last_grounded_time + 0.085)
		can_leave_ground = true;

	if ((self.map_control_flags & PLAYER_CONTROL_FROZEN)
	    || !can_leave_ground
	    || !(self.flags & FL_JUMPRELEASED)
		|| self.downed
		|| self.dive ) {
		return;
	}

	self.flags = self.flags - (self.flags & FL_JUMPRELEASED);

	if (self.button2)
		self.button2 = 0;

	self.oldz = self.origin_z;
	self.xziel_jump_buffer_until = 0;

	/* Original NZ:P: 230 u/s at 800 u/s^2 gravity (~33 units apex).
	   Xziel modern profile: 265 u/s at 1.30x player gravity
	   (~33.8 units apex), preserving map traversal while producing a shorter,
	   heavier modern-shooter arc. */
	if (modern_movement)
		self.velocity_z = 265;
	else
		self.velocity_z = 230;
}'''
if "shorter,\n\t   heavier modern-shooter arc" not in text:
    text = replace_once(text, old_jump, new_jump, "PlayerJump")

old_check = r'''void(float override) JumpCheck =
{
	if (self.map_control_flags & PLAYER_CONTROL_FROZEN)
		return;

#ifndef FTE

	override = 0;

#endif // FTE

	if(self.button2 || override) {
		if (self.downed)
			return;
			
		if (self.stance == PLAYER_STANCE_STAND) {
			PlayerJump();
		} else if (self.view_ofs_z == self.new_ofs_z && (self.flags & FL_ONGROUND)) {
			Player_SetStance(self, PLAYER_STANCE_STAND, true);
		}
	} else
		self.flags = self.flags | FL_JUMPRELEASED;
}'''

new_check = r'''void(float override) JumpCheck =
{
	if (self.map_control_flags & PLAYER_CONTROL_FROZEN)
		return;

#ifndef FTE

	override = 0;

#endif // FTE

	float modern_movement = cvar("xziel_modern_movement") >= 0.5;

	if (self.flags & FL_ONGROUND)
		self.xziel_last_grounded_time = time;

	if(self.button2 || override) {
		if (self.downed)
			return;

		if (modern_movement)
			self.xziel_jump_buffer_until = time + 0.090;

		if (self.stance == PLAYER_STANCE_STAND) {
			PlayerJump();
		} else if (self.view_ofs_z == self.new_ofs_z && (self.flags & FL_ONGROUND)) {
			Player_SetStance(self, PLAYER_STANCE_STAND, true);
		}
	} else {
		self.flags = self.flags | FL_JUMPRELEASED;

		/* A quick tap just before landing is remembered briefly. This is
		   standard modern-controller forgiveness, not auto-bunnyhopping:
		   FL_JUMPRELEASED still requires a real release between jumps. */
		if (modern_movement &&
			self.xziel_jump_buffer_until > time &&
			self.stance == PLAYER_STANCE_STAND)
			PlayerJump();
	}
}'''
if "standard modern-controller forgiveness" not in text:
    text = replace_once(text, old_check, new_check, "JumpCheck")

spawn_anchor = '''\tself.new_ofs_z = self.view_ofs_z;
\tself.oldz = self.origin_z;
'''
spawn_repl = '''\tself.new_ofs_z = self.view_ofs_z;
\tself.oldz = self.origin_z;
\tself.xziel_jump_buffer_until = 0;
\tself.xziel_last_grounded_time = time;
'''
if "self.xziel_last_grounded_time = time;" not in text[text.find("void() PlayerSpawn"):]:
    text = replace_once(text, spawn_anchor, spawn_repl, "PlayerSpawn movement init")

player.write_text(text, encoding="utf-8")
print("Applied Xziel modern jump arc, coyote time and jump buffer.")
