#!/usr/bin/env python3
"""Xziel v0.26: deterministic four-player co-op spawn layout.

NZ:P normally randomizes the first four character spawn entities. For online
co-op we keep the map-authored four spawn positions but bind player slots
1..4 to spawn classes 1..4. This prevents clients from stacking on the same
spawn and keeps the starting group in the map's intended spawn area.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_quakec_multiplayer_v026.py <quakec-root>")

root = Path(sys.argv[1])
path = root / "source" / "server" / "player" / "player_core.qc"
text = path.read_text(encoding="utf-8")

anchor = """#endif // FTE

	// Assign a location
	while(!found_viable_spawn) {
"""
insert = """#endif // FTE

	// Online/co-op: make the first four player slots deterministic. The map's
	// authored spawn1..spawn4 positions are already designed as a nearby start
	// group, so each network player gets a stable, distinct location.
	if (coop && self.playernum >= 1 && self.playernum <= 4) {
		switch(self.playernum) {
			case 1: spawn_point = find(world, classname, SPAWN_1_CLASS); break;
			case 2: spawn_point = find(world, classname, SPAWN_2_CLASS); break;
			case 3: spawn_point = find(world, classname, SPAWN_3_CLASS); break;
			case 4: spawn_point = find(world, classname, SPAWN_4_CLASS); break;
		}

		if (spawn_point != world) {
			float occupied = false;
			entity nearby = findradius(spawn_point.origin, 32);
			while (nearby != world) {
				if (nearby.classname == "player" && nearby != self)
					occupied = true;
				nearby = nearby.chain;
			}
			if (!occupied)
				found_viable_spawn = true;
		}
	}

	// Assign a location
	while(!found_viable_spawn) {
"""
if "Online/co-op: make the first four player slots deterministic" not in text:
    if anchor not in text:
        raise SystemExit("Could not find Player_PickSpawnPoint location anchor")
    text = text.replace(anchor, insert, 1)

# Xziel online third-person ADS pose.
# NZ:P's stock player model has no dedicated ADS state: standing players always
# fall back to frame 0, so remote clients cannot visually tell aim-in/aim-out.
# Reuse the existing standing fire-ready pose (frame 9) while a co-op player is
# holding ADS and no higher-priority reload/fire/melee animation owns the model.
# Firing still advances 9->10 through the stock PAnim_Fire path.
idle_old = """		} else {
			// Stand still so Crouch Walk isn't stuck in place
			switch(self.stance) {
				case 2: self.frame = 0; break;
				case 1: self.frame = 115; break;
				case 0: self.frame = 162; break;
			}
"""
idle_new = """		} else {
			// Stand still so Crouch Walk isn't stuck in place.
			// Online co-op keeps a visible fire-ready pose while ADS is held so
			// other players can actually see aim-in / aim-out state.
			switch(self.stance) {
				case 2:
					if (coop && self.zoom && self.zoom != 3)
						self.frame = 9;
					else
						self.frame = 0;
					break;
				case 1: self.frame = 115; break;
				case 0: self.frame = 162; break;
			}
"""
if "Online co-op keeps a visible fire-ready pose while ADS is held" not in text:
    if idle_old not in text:
        raise SystemExit("Could not find third-person idle animation anchor")
    text = text.replace(idle_old, idle_new, 1)

# Vril/classic-protocol player footsteps.
# Upstream only emits human footsteps inside #ifdef FTE, which means Android
# clients can see remote movement but never receive a player footstep sound.
# Keep the original FTE path untouched and add the equivalent authoritative
# SSQC sound emission for non-FTE builds, using server velocity as movement
# evidence. Sound_PlaySound/PLAYSOUND then replicates the real svc_sound packet
# to every observer.
footstep_anchor = """#endif // FTE
	
	// Health Regeneration
"""
footstep_insert = """#endif // FTE

#ifndef FTE
	// Networked player footsteps for Vril/classic protocol builds.
	if ((vlen(self.velocity) > 20) &&
		((time - self.lastsound_time > 0.4) ||
		 (time - self.lastsound_time > 0.3 && self.sprinting)) &&
		(self.flags & FL_ONGROUND))
	{
		local float ran = random();
		if (ran > 0.8)
			Sound_PlaySound(self, "sounds/player/footstep1.wav", SOUND_TYPE_PLAYER_FOOTSTEP, SOUND_PRIORITY_PLAYALWAYS);
		else if (ran > 0.6)
			Sound_PlaySound(self, "sounds/player/footstep2.wav", SOUND_TYPE_PLAYER_FOOTSTEP, SOUND_PRIORITY_PLAYALWAYS);
		else if (ran > 0.4)
			Sound_PlaySound(self, "sounds/player/footstep3.wav", SOUND_TYPE_PLAYER_FOOTSTEP, SOUND_PRIORITY_PLAYALWAYS);
		else if (ran > 0.2)
			Sound_PlaySound(self, "sounds/player/footstep4.wav", SOUND_TYPE_PLAYER_FOOTSTEP, SOUND_PRIORITY_PLAYALWAYS);
		else
			Sound_PlaySound(self, "sounds/player/footstep5.wav", SOUND_TYPE_PLAYER_FOOTSTEP, SOUND_PRIORITY_PLAYALWAYS);
		self.lastsound_time = time;
	}
#endif // !FTE
	
	// Health Regeneration
"""
if "Networked player footsteps for Vril/classic protocol builds" not in text:
    if footstep_anchor not in text:
        raise SystemExit("Could not find non-FTE footstep insertion anchor")
    text = text.replace(footstep_anchor, footstep_insert, 1)

# The sound must be in the precache table on non-FTE too. Make the five player
# footsteps unconditional; FTE continues to precache the same assets once.
main_path = root / "source" / "server" / "main.qc"
main = main_path.read_text(encoding="utf-8")
precache_old = """#ifdef FTE

	precache_sound("sounds/player/footstep1.wav");
	precache_sound("sounds/player/footstep2.wav");
	precache_sound("sounds/player/footstep3.wav");
	precache_sound("sounds/player/footstep4.wav");
	precache_sound("sounds/player/footstep5.wav");

#endif // FTE

	precache_sound("sounds/player/jump.wav");
"""
precache_new = """	precache_sound("sounds/player/footstep1.wav");
	precache_sound("sounds/player/footstep2.wav");
	precache_sound("sounds/player/footstep3.wav");
	precache_sound("sounds/player/footstep4.wav");
	precache_sound("sounds/player/footstep5.wav");

	precache_sound("sounds/player/jump.wav");
"""
if "Xziel player footsteps are networked on Vril" not in main:
    if precache_old not in main:
        raise SystemExit("Could not find FTE-only player footstep precache block")
    main = main.replace(precache_old,
        "/* Xziel player footsteps are networked on Vril too. */\n" + precache_new, 1)
main_path.write_text(main, encoding="utf-8")

# Mystery Box co-op pickup sharing.
# Stock NZ:P only lets the player who paid collect the revealed gun. Online
# co-op keeps the roll/animation authoritative on the host, but once the gun is
# fully presented any living player may take it. First successful pickup wins,
# then the authoritative box closes for everyone.
mbox_path = root / "source" / "server" / "entities" / "mystery_box.qc"
mbox = mbox_path.read_text(encoding="utf-8")

owner_prompt = '''	if (self.boxstatus == 2 && self.owner == other) {
		other.useprint_touch = GetWeaponName(self.boxweapon.weapon, -1);
		Player_UseprintWithWait(other, self, self.useprint_index_2, 0);
	}
'''
shared_prompt = '''	if (self.boxstatus == 2 && self.owner != world) {
		other.useprint_touch = GetWeaponName(self.boxweapon.weapon, -1);
		Player_UseprintWithWait(other, self, self.useprint_index_2, 0);
	}
'''
if "First successful co-op pickup wins" not in mbox:
    if owner_prompt not in mbox:
        raise SystemExit("Could not find Mystery Box owner-only useprint anchor")
    mbox = mbox.replace(owner_prompt, shared_prompt, 1)

    owner_take = '''		if (self.boxstatus == 2)
		{
			if (self.owner == other)
			{
				other.reload_delay = 0;
				self.owner = world;
				Sound_PlaySound(self, "sounds/misc/ching.wav", SOUND_TYPE_ENV_CHING, SOUND_PRIORITY_PLAYALWAYS);
				tempe = self;
				self = other;

				Weapon_GiveWeapon(tempe.boxweapon.weapon, 0, 0, 0);
				self = tempe;
				MBOX_FreeEnt(self.boxweapon);
				MBOX_PlayCloseAnimation();
			}
		}
'''
    shared_take = '''		if (self.boxstatus == 2 && self.owner != world)
		{
			/* First successful co-op pickup wins. The buyer paid for the spin,
			   but any living teammate may claim the revealed weapon. This runs
			   entirely on SSQC, so weapon ownership, box close animation and
			   pickup sound replicate from the authoritative host. */
			other.reload_delay = 0;
			self.owner = world;
			Sound_PlaySound(self, "sounds/misc/ching.wav", SOUND_TYPE_ENV_CHING, SOUND_PRIORITY_PLAYALWAYS);
			tempe = self;
			self = other;

			Weapon_GiveWeapon(tempe.boxweapon.weapon, 0, 0, 0);
			self = tempe;
			MBOX_FreeEnt(self.boxweapon);
			MBOX_PlayCloseAnimation();
		}
'''
    if owner_take not in mbox:
        raise SystemExit("Could not find Mystery Box owner-only pickup block")
    mbox = mbox.replace(owner_take, shared_take, 1)

mbox_path.write_text(mbox, encoding="utf-8")

path.write_text(text, encoding="utf-8")
print("Applied Xziel v0.26 online spawns + ADS pose + shared Mystery Box pickup.")
