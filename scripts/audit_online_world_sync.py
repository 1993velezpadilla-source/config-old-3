#!/usr/bin/env python3
"""Audit Xziel's online world-sync contract on the patched NZ:P QuakeC tree.

The Android internet transport tunnels Vril's native datagrams. This audit
guards the gameplay side of that contract: shared-world interactions must stay
in authoritative SSQC/server code so the host owns state and every connected
client receives the same entity/sound/effect updates.
"""
from pathlib import Path
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: audit_online_world_sync.py <patched-quakec-root>")

root = Path(sys.argv[1])
checks = []

def require(path: str, needle: str, label: str):
    p = root / path
    if not p.exists():
        raise SystemExit(f"missing required server file: {path}")
    text = p.read_text(encoding="utf-8")
    ok = needle in text
    checks.append({"label": label, "path": path, "ok": ok, "needle": needle})
    if not ok:
        raise SystemExit(f"online world-sync audit failed: {label}: {needle!r} not found in {path}")
    return text

# Mystery Box roll, floating weapon, animation and pickup all live in SSQC.
mbox = require(
    "source/server/entities/mystery_box.qc",
    "void() MBOX_Touch",
    "Mystery Box interaction is host-authoritative SSQC",
)
require(
    "source/server/entities/mystery_box.qc",
    "First successful co-op pickup wins",
    "Unclaimed Mystery Box weapon can be taken by any teammate",
)
if "self.boxstatus == 2 && self.owner == other" in mbox:
    raise SystemExit("Mystery Box still contains owner-only pickup gating")
checks.append({
    "label": "Mystery Box has no owner-only pickup gate",
    "path": "source/server/entities/mystery_box.qc",
    "ok": True,
})

# Grenades are real server entities with server-side physics/explosion.
grenade = require(
    "source/server/weapons/weapon_core.qc",
    "void() W_ThrowGrenade",
    "Grenade throw is server-authoritative",
)
for needle, label in [
    ("nade = spawn ()", "Grenade creates a networked server entity"),
    ("nade.think = GrenadeExplode", "Grenade explosion timer is server-owned"),
    ('setmodel (nade, "models/weapons/grenade/g_grenade.mdl")',
     "Grenade world model is replicated from server entity state"),
]:
    if needle not in grenade:
        raise SystemExit(f"online world-sync audit failed: {label}")
    checks.append({"label": label, "path": "source/server/weapons/weapon_core.qc", "ok": True})

# Footsteps and shared game sounds are emitted by SSQC through the engine sound
# builtin, which is serialized by the server protocol to clients in range.
player = require(
    "source/server/player/player_core.qc",
    "SOUND_TYPE_PLAYER_FOOTSTEP",
    "Player footsteps originate on authoritative server",
)
sound = require(
    "source/server/utilities/sound_helper.qc",
    "void(entity source_ent, string path, float type, float priority) Sound_PlaySound",
    "Shared sound routing originates on authoritative server",
)
for needle, label in [
    ("PLAYSOUND(source_ent", "Sound helper routes events through engine sound builtin"),
    ("SOUND_TYPE_WEAPON_FIRE", "Weapon fire has shared server sound category"),
    ("SOUND_TYPE_PLAYER_FOOTSTEP", "Footsteps have shared server sound category"),
    ("SOUND_TYPE_WEAPON_EXPLODE", "Explosions have shared server sound category"),
]:
    if needle not in sound:
        raise SystemExit(f"online world-sync audit failed: {label}")
    checks.append({"label": label, "path": "source/server/utilities/sound_helper.qc", "ok": True})

# Zombie hit blood, damage and dismemberment are decided in SSQC. Clients only
# render the resulting networked entity/effect state.
weapon = require(
    "source/server/weapons/weapon_core.qc",
    "SpawnBlood",
    "Zombie bullet-hit blood is triggered server-side",
)
for needle, label in [
    ("DamageHandler", "Zombie/player weapon damage is server-authoritative"),
    ("Zombie_HeadCanGib", "Zombie head-gib decision is server-authoritative"),
]:
    if needle not in weapon:
        raise SystemExit(f"online world-sync audit failed: {label}")
    checks.append({"label": label, "path": "source/server/weapons/weapon_core.qc", "ok": True})

# World purchases and interactables stay in server entity code.
for path, needle, label in [
    ("source/server/entities/doors.qc", "Player_RemoveScore", "Doors/buyables mutate state on server"),
    ("source/server/entities/wall_weapon.qc", "Weapon_GiveWeapon", "Wall weapon purchase grants weapon on server"),
    ("source/server/entities/pack_a_punch.qc", "PAP_UpgradeWeapon", "Pack-a-Punch upgrade state is server-owned"),
]:
    require(path, needle, label)

report = {
    "ok": True,
    "contract": "single authoritative host world; clients consume native Vril replication",
    "checks": checks,
}
print(json.dumps(report, indent=2))
