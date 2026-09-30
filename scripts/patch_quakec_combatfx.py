#!/usr/bin/env python3
"""Add Xziel mobile combat feedback to NZ:P QuakeC."""
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_quakec_combatfx.py <quakec-root>")

root = Path(sys.argv[1])

# Standard protocol: 58 is the next unused server->client message after
# SVC_REGISTERUSEPRINT (57) in current NZ:P/Vril.
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

hit_pattern = re.compile(
    r'(?m)^(?P<indent>[ \t]*)if\s*\(victim\.classname\s*==\s*"ai_zombie"\s*\|\|\s*'
    r'victim\.classname\s*==\s*"ai_dog"\s*\)\s*\{\s*$'
)
if "nzp_damage_number(attacker" not in text:
    match = hit_pattern.search(text)
    if not match:
        raise SystemExit("Could not find zombie damage branch")
    indent = match.group("indent") + "\t"
    insertion = (
        "\n"
        + indent + "/* XZIEL mobile floating damage feedback. */\n"
        + indent + 'if (attacker.classname == "player" && d_style != DMG_TYPE_OTHER && damage > 0)\n'
        + indent + "\tnzp_damage_number(attacker, damage, d_style == DMG_TYPE_HEADSHOT);\n"
    )
    text = text[:match.end()] + insertion + text[match.end():]
damage.write_text(text, encoding="utf-8")

print("Patched QuakeC Xziel combat feedback.")
