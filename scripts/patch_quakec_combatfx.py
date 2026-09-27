#!/usr/bin/env python3
"""Add Xziel mobile combat feedback to NZ:P QuakeC."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_quakec_combatfx.py <quakec-root>")

root = Path(sys.argv[1])

# Standard protocol: current Vril uses svc_hudconfig=58, so Xziel damage
# feedback lives at 59 to avoid colliding with the upstream HUD packet.
defs = root / "source/server/defs/standard.qc"
text = defs.read_text(encoding="utf-8")
anchor = "#define \tSVC_ACHIEVEMENT \t\t\t52\n"
if "SVC_XZIELDAMAGE" not in text:
    if anchor not in text:
        raise SystemExit("Could not find SVC_ACHIEVEMENT protocol anchor")
    text = text.replace(anchor, anchor + "#define     SVC_XZIELDAMAGE             59\n", 1)
defs.write_text(text, encoding="utf-8")

# Reliable one-client damage number event. FTE is intentionally a no-op here;
# Xziel Android uses the Standard Vril protocol path.
clientfuncs = root / "source/server/clientfuncs.qc"
text = clientfuncs.read_text(encoding="utf-8")
anchor = "void(entity who, float death_marker) nzp_hitmarker =\n"
if "nzp_damage_number" not in text:
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit("Could not find nzp_hitmarker insertion point")
    block = r'''
//
// nzp_damage_number(who, damage, critical)
// Xziel mobile floating combat text. Body damage is white, critical/headshot
// damage is gold on the client.
//
void(entity who, float damage, float critical) nzp_damage_number =
{
#ifndef FTE
	msg_entity = who;
	WriteByte(MSG_ONE, SVC_XZIELDAMAGE);
	WriteLong(MSG_ONE, rint(damage));
	WriteByte(MSG_ONE, critical);
#endif
};

'''
    text = text[:idx] + block + text[idx:]
clientfuncs.write_text(text, encoding="utf-8")

damage = root / "source/server/damage.qc"
text = damage.read_text(encoding="utf-8")
if "void(entity who, float damage, float critical) nzp_damage_number;" not in text:
    insert_at = text.find("void(entity attacker, float d_style) DieHandler")
    if insert_at < 0:
        raise SystemExit("Could not find damage handler declaration point")
    text = text[:insert_at] + (
        "void(entity who, float damage, float critical) nzp_damage_number;\n\n"
    ) + text[insert_at:]

hit_anchor = '''\tif (victim.classname == "ai_zombie" || victim.classname == "ai_dog") {\n'''
hit_repl = '''\tif (victim.classname == "ai_zombie" || victim.classname == "ai_dog") {\n\t\t/* Mobile COD-style floating damage numbers. Report the actual weapon\n\t\t   damage request for every legitimate player hit, including the fatal\n\t\t   shot. The client owns presentation/timing only. */\n\t\tif (attacker.classname == "player" && d_style != DMG_TYPE_OTHER && damage > 0)\n\t\t\tnzp_damage_number(attacker, damage, d_style == DMG_TYPE_HEADSHOT);\n\n'''
if "nzp_damage_number(attacker" not in text:
    if hit_anchor not in text:
        raise SystemExit("Could not find zombie damage branch")
    text = text.replace(hit_anchor, hit_repl, 1)
damage.write_text(text, encoding="utf-8")

print("Patched QuakeC Xziel combat feedback.")
