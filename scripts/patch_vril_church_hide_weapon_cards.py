#!/usr/bin/env python3
"""XZIEL Church Mini: remove the three floating gun cards, not weapon swapping.

Presentation-only HUD adjustment:
  - Disable the three-slot weapon-card rail entirely (game and HUD editor).
  - Remove its now-invisible touch interception zones.
  - Restore ONE small, user-approved SWAP button for changing guns.
  - Preserve reload, ammo logic, damage, gyroscope, ADS, original gun models,
    player stats and all other HUD controls.
Applied AFTER mobile_v022 + approved_touch_skins and only in CHURCH_MINI.
"""
from pathlib import Path
import sys

if len(sys.argv)!=2:
    raise SystemExit("usage: patch_vril_church_hide_weapon_cards.py <vril-root>")
root=Path(sys.argv[1])
hud=root/"source/render/r_hud.c"
sdl=root/"source/platform/sdl/sys_sdl.c"
h=hud.read_text(encoding="utf-8")
s=sdl.read_text(encoding="utf-8")

def replace_function(source, signature, replacement):
    if source.count(signature)!=1:
        raise RuntimeError("Expected EXACTLY one anchor "+signature+
                           ", found "+str(source.count(signature)))
    start=source.index(signature)
    brace=source.find("{",start+len(signature))
    if brace<0:
        raise RuntimeError("Missing function opening brace "+signature)
    depth=0
    end=None
    for index in range(brace,len(source)):
        ch=source[index]
        if ch=="{":
            depth+=1
        elif ch=="}":
            depth-=1
            if depth==0:
                end=index+1
                break
    if end is None:
        raise RuntimeError("Unclosed C function "+signature)
    return source[:start]+replacement+source[end:]

# Keep this symbol present, but do not draw 3 ugly overlapping panels.
# We deliberately do NOT touch the individual weapon-card implementation or
# weapon state: another map can still use that UI when this patch is disabled.
h=replace_function(h,"static void Xziel_DrawWeaponStrip(qboolean editor)",
'''static void Xziel_DrawWeaponStrip(qboolean editor)
{
    (void)editor;
    /* CHURCH_MINI: author removed the 3 weapon cards from the display. */
}''')
if h.count("Xziel_DrawWeaponStrip(editor);")!=1:
    raise RuntimeError("Weapon strip draw call changed; refusing blind patch")

# Existing source already loaded the approved hud_swap.webp texture.
glyph='    if (!strcmp(label1, "SLIDE")) return xziel_approved_skin_slide;'
if h.count(glyph)!=1:
    raise RuntimeError("Approved button mapping changed; SWAP skin unavailable")
h=h.replace(glyph,glyph+'\n    if (!strcmp(label1, "SWAP")) return xziel_approved_skin_swap;',1)

# The SWAP role still executes the original VRIL native weapon switch.
# Draw a single compact authored button, not another weapon-card system.
call='\tXziel_DrawWeaponStrip(editor);'
if h.count(call)!=1:
    raise RuntimeError("Draw injection anchor missing")
button='''\tXziel_DrawTouchButton(xziel_hud_switch_x.value, xziel_hud_switch_y.value,
\t\t0.041f, "SWAP", "", xziel_mobile_switch_pressed, editor);

'''
h=h.replace(call,button+call,1)

# Invisible weapon cards must NOT continue swallowing touch input or preventing
# camera swipes. Do not delete game actions or unhook weapon ownership.
s=replace_function(s,
    "static qboolean Xziel_WeaponStripHit(float x, float y, int slot)",
'''static qboolean Xziel_WeaponStripHit(float x, float y, int slot)
{
    (void)x; (void)y; (void)slot;
    return false; /* no phantom hit areas after card removal */
}''')

# The weapon-switch button used to exist in the early native HUD but was lost
# when weapon cards replaced it. Give it a valid hitbox in regular gameplay.
sig="static xziel_touch_role_t Xziel_RoleForPoint(float x, float y)"
p=s.index(sig)
q=s.index("static xziel_touch_role_t Xziel_HudEditorRole",p)
part=s[p:q]
anchor="\tfloat hs = xziel_mobile_hud_scale.value;\n"
if part.count(anchor)!=1:
    raise RuntimeError("Expected 1 role/scale anchor")
part=part.replace(anchor,anchor+'''\tif (Xziel_IsInside(x, y, xziel_hud_switch_x.value,
\t\txziel_hud_switch_y.value, 0.052f * hs)) return XZ_TOUCH_SWITCH;
''',1)
s=s[:p]+part+s[q:]

# Same SWAP button is selectable and position-adjustable in HUD editor.
sig="static xziel_touch_role_t Xziel_HudEditorRole"
p=s.index(sig)
q=s.index("static void Xziel_HudEditorSetPosition",p)
part=s[p:q]
if part.count(anchor)!=1:
    raise RuntimeError("Expected 1 editor/scale anchor")
part=part.replace(anchor,anchor+'''\tif (Xziel_IsInside(x, y, xziel_hud_switch_x.value,
\t\txziel_hud_switch_y.value, 0.061f * hs)) return XZ_TOUCH_SWITCH;
''',1)
s=s[:p]+part+s[q:]

sig="static void Xziel_HudEditorSetPosition"
p=s.index(sig)
q=s.index("static void Xziel_FingerDown",p)
part=s[p:q]
pos='\tcase XZ_TOUCH_PAUSE: Cvar_SetValue("xziel_hud_pause_x", x); Cvar_SetValue("xziel_hud_pause_y", y); break;'
if part.count(pos)!=1:
    raise RuntimeError("Expected 1 HUD editor PAUSE anchor")
part=part.replace(pos,pos+'\n'+
    '\tcase XZ_TOUCH_SWITCH: Cvar_SetValue("xziel_hud_switch_x", x); Cvar_SetValue("xziel_hud_switch_y", y); break;',1)
s=s[:p]+part+s[q:]

if s.count('case XZ_TOUCH_SWITCH:')<2:
    raise RuntimeError("Native switch role unavailable after patch")
if "xziel_approved_skin_swap" not in h:
    raise RuntimeError("User-authorized SWAP skin was not loaded")

hud.write_text(h,encoding="utf-8")
sdl.write_text(s,encoding="utf-8")
print("XZIEL_CHURCH_NO_GUN_CARDS_GREEN")
print("XZIEL_ONE_APPROVED_SWAP_BUTTON_GREEN")
print("XZIEL_NO_INVISIBLE_CARD_HITBOXES_GREEN")
