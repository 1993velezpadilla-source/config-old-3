#!/usr/bin/env python3
"""Xziel v0.22 QuakeC gameplay pass.

- ADS walking slider becomes authoritative server maxspeed rather than being
  double-damped by client input + stock 0.5 ADS cap.
- Mobile crouch reliably becomes slide when sprint intent / speed says the
  player is sprinting, even if the sprint network state changes that frame.
- Optional modern zombie locomotion smooths velocity/turn transitions while
  preserving stock NZ:P animation frames, melee, crawl, barriers and pathing.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_quakec_mobile_v022.py <quakec-root>")

root = Path(sys.argv[1])
player = root / "source" / "server" / "player" / "player_core.qc"
weapon = root / "source" / "server" / "weapons" / "weapon_core.qc"
ai = root / "source" / "server" / "ai" / "ai_core.qc"

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
    return src[:start] + replacement + src[end:]

# ---------------------------------------------------------------------------
# ADS walking: stock NZ:P hard-caps all ADS to 50% maxspeed. The Android
# slider now replaces that cap directly; GetWeaponWalkSpeed still applies the
# real NZ:P per-weapon weight after it, preserving pistol/rifle/heavy identity.
# ---------------------------------------------------------------------------
text = player.read_text(encoding="utf-8")
old = """\t\t} else if (self.zoom != 3) {
\t\t\tself.maxspeed *= 0.5;
\t\t} 
"""
new = """\t\t} else if (self.zoom != 3) {
\t\t\tfloat xziel_ads_walk = cvar("xziel_mobile_ads_move_sensitivity");
\t\t\tif (xziel_ads_walk > 0) {
\t\t\t\tif (xziel_ads_walk < 0.35) xziel_ads_walk = 0.35;
\t\t\t\tif (xziel_ads_walk > 1.75) xziel_ads_walk = 1.75;
\t\t\t\tself.maxspeed *= xziel_ads_walk;
\t\t\t} else {
\t\t\t\tself.maxspeed *= 0.5;
\t\t\t}
\t\t} 
"""
if old not in text:
    raise SystemExit("Could not find stock ADS maxspeed block")
text = text.replace(old, new, 1)
player.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# Reliable sprint -> crouch slide.
# ---------------------------------------------------------------------------
text = weapon.read_text(encoding="utf-8")

slide_think = r'''void() Xziel_MobileSlideThink =
{
	if (self.xziel_slide_end <= 0)
		return;

	if (self.xziel_slide_end <= time ||
		self.downed || self.dive || !(self.flags & FL_ONGROUND)) {
		self.xziel_slide_end = 0;
		return;
	}

	float remaining = (self.xziel_slide_end - time) / 0.58;
	if (remaining < 0) remaining = 0;
	if (remaining > 1) remaining = 1;

	float target_speed = 88 + (178 * remaining);
	vector horizontal = [self.velocity_x, self.velocity_y, 0];
	float current_speed = vlen(horizontal);

	/* Deliberately control ordinary slide momentum so it visibly decays.
	   Very large external knockback/explosion velocity is left untouched. */
	if (current_speed < 430) {
		self.velocity_x = self.xziel_slide_dir_x * target_speed;
		self.velocity_y = self.xziel_slide_dir_y * target_speed;
	}
};'''
text = replace_function(text, "void() Xziel_MobileSlideThink", slide_think)

slide = r'''void() Xziel_MobileCrouchSlide =
{
	if (self.downed || !(self.flags & FL_ONGROUND))
		return;

	vector horizontal = [self.velocity_x, self.velocity_y, 0];
	float speed = vlen(horizontal);
	float sprint_intent =
		self.sprinting ||
		self.sprintflag ||
		(speed >= 145 && self.stance == PLAYER_STANCE_STAND);

	/* A stance transition can briefly outlive the sprint flag. Do not throw
	   away an obvious high-speed slide request just because view height is
	   between two frames. Normal crouch still respects stance-transition
	   safety. */
	if (!sprint_intent) {
		if (self.changestance == true || self.new_ofs_z != self.view_ofs_z)
			return;
		Change_StanceToggle();
		return;
	}

	makevectors(self.v_angle);
	if (speed < 8) {
		self.xziel_slide_dir = v_forward;
		self.xziel_slide_dir_z = 0;
	} else {
		self.xziel_slide_dir = normalize(horizontal);
		self.xziel_slide_dir_z = 0;
	}

	W_AimOut();
	if (self.sprinting)
		W_SprintStop();
	self.sprintflag = false;
	self.sprinting = false;
	self.zoom = 0;

	Player_SetStance(self, PLAYER_STANCE_CROUCH, false);
	self.xziel_slide_end = time + 0.58;

	self.velocity_x = self.xziel_slide_dir_x * 266;
	self.velocity_y = self.xziel_slide_dir_y * 266;
};'''
text = replace_function(text, "void() Xziel_MobileCrouchSlide", slide)
weapon.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# Modern zombie locomotion layer.
# The iconic stock frame sets and state machine remain untouched. We only stop
# hard-resetting planar velocity every animation step and ease toward the same
# root-motion target while a normal standing zombie chases indoors.
# Crawlers, dogs, window/barrier traversal, falls, melee and deaths stay stock.
# ---------------------------------------------------------------------------
text = ai.read_text(encoding="utf-8")

walk_to = r'''void(float dist, vector vec) do_walk_to_vec =
{
	if(dist == 0)
		return;

	self.ideal_yaw = vectoyaw(vec - self.origin);
	if(self.outside == false)
		push_away_zombies();

	ChangeYaw();

	float len = vlen(self.origin - vec);
	if(dist > len)
		dist = len;

	vector desired_dir = normalize(vec - self.origin);
	vector new_velocity;

	float modern =
		cvar("xziel_modern_zombies") >= 0.5 &&
		self.classname == "ai_zombie" &&
		self.crawling != true &&
		self.outside == FALSE;

	if (modern) {
		/* Movement direction follows the path strongly, but a small facing
		   contribution removes the old sideways skating when ChangeYaw is
		   still catching up. */
		makevectors(self.angles);
		vector facing = v_forward;
		facing_z = 0;
		vector move_dir = normalize(desired_dir * 0.82 + facing * 0.18);
		float blend = (self.walktype >= 4) ? 0.72 : 0.56;
		float target_speed = dist * 10;

		new_velocity = move_dir * target_speed;
		new_velocity_x =
			self.velocity_x + (new_velocity_x - self.velocity_x) * blend;
		new_velocity_y =
			self.velocity_y + (new_velocity_y - self.velocity_y) * blend;
		new_velocity_z = self.velocity_z;
	} else {
		new_velocity = desired_dir * dist * 10;
		new_velocity_z = self.velocity_z;
	}

	self.velocity = new_velocity;
};'''
# Upstream QuakeC (2026) now has AI_PathLookahead, AI_PathVelocity and
# AI_CrowdVelocity. Never overwrite that collision-aware pathing with a
# deprecated pre-2026 implementation referencing push_away_zombies().
# Smooth only the final XY velocity; preserve validated upstream navigation.
ai_signature = "void(float dist, vector vec) do_walk_to_vec"
ai_start = text.find(ai_signature)
ai_end = text.find("void(float dist) do_walk", ai_start)
if ai_start < 0 or ai_end < 0:
    raise SystemExit("NZP AI movement function not found")
ai_function = text[ai_start:ai_end]
upstream_velocity = """\tnew_velocity_z = self.velocity_z;
\tself.velocity = new_velocity;"""
smooth_velocity = """\t/* Android opt-in smooth XY transitions; keep upstream crowd/path vectors. */
\tif (cvar("xziel_modern_zombies") >= 0.5
\t    && self.classname == "ai_zombie"
\t    && self.crawling != true && self.outside == FALSE
\t    && dist > 0) {
\t\tnew_velocity_x = self.velocity_x + (new_velocity_x - self.velocity_x) * 0.70;
\t\tnew_velocity_y = self.velocity_y + (new_velocity_y - self.velocity_y) * 0.70;
\t}
\tnew_velocity_z = self.velocity_z;
\tself.velocity = new_velocity;"""
if "AI_PathLookahead" not in ai_function:
    raise SystemExit("Upstream AI_PathLookahead contract unavailable; refusing to downgrade zombie pathing")
if ai_function.count(upstream_velocity) != 1:
    raise SystemExit("Upstream AI velocity commit anchor changed")
ai_function = ai_function.replace(upstream_velocity, smooth_velocity, 1)
text = text[:ai_start] + ai_function + text[ai_end:]
print("XZIEL_ZOMBIE_AI_UPSTREAM_PATH_LOOKAHEAD_PRESERVED")

zombie_walk = r'''void(float dist) Zombie_Walk =
{
	dist = Gamemode_GetAIWalkSpeed(dist, self.classname);

	float modern =
		cvar("xziel_modern_zombies") >= 0.5 &&
		self.classname == "ai_zombie" &&
		self.crawling != true &&
		self.outside == FALSE;

	/* Stock code zeroes X/Y every animation step, which is the biggest source
	   of robotic stop/start motion. Keep that exact behavior for all special
	   traversal and Classic mode. Attack frames pass dist=0 and must stop. */
	if (!modern || dist <= 0) {
		self.velocity_x = 0;
		self.velocity_y = 0;
	}

	if (!(self.flags & FL_ONGROUND) && self.watertype != CONTENT_WATER) {
		if (!self.droptime) {
			self.droptime = time + 1;
		} else if (self.droptime < time) {
			self.droptime = 0;
			if (self.classname != "ai_dog")
				self.th_fall();
			return;
		}
	}

	if(self.outside == TRUE) {
		Window_Walk(dist);
		return;
	}

	if(self.outside == 2) {
		Window_Hop(dist);
		return;
	}

	if(self.outside == FALSE) {
		if(self.goalentity == self.enemy) {
			if(vlen(self.origin - self.enemy.origin) < 60)
				return;
		}
	}

	do_walk(dist);
};'''
# Keep NZ:P super-sprint, fall recovery, crawler, dog separation,
# Window_Walk and window hop logic intact. Smooth by stopping per-frame planar
# hard reset for walking zombies ONLY; nothing else uses altered behavior.
walk_start = text.find("void(float dist) Zombie_Walk")
walk_end = text.find("void() Zombie_AI", walk_start)
if walk_start < 0 or walk_end < 0:
    raise SystemExit("Upstream Zombie_Walk function not found")
walk_function = text[walk_start:walk_end]
old_stop = """\tself.velocity_x = 0;
\tself.velocity_y = 0;"""
new_stop = """\tif (!(cvar("xziel_modern_zombies") >= 0.5
\t    && self.classname == "ai_zombie"
\t    && self.crawling != true && self.outside == FALSE
\t    && dist > 0)) {
\t\tself.velocity_x = 0;
\t\tself.velocity_y = 0;
\t}"""
if walk_function.count(old_stop) != 1:
    raise SystemExit("Upstream zombie planar reset anchor changed")
walk_function = walk_function.replace(old_stop, new_stop, 1)
text = text[:walk_start] + walk_function + text[walk_end:]

ai.write_text(text, encoding="utf-8")
print("Applied Xziel v0.22 ADS walking, reliable slide and modern zombie motion.")
