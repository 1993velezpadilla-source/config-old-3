#!/usr/bin/env python3
"""Mount already-approved latest_12 touch skins onto the native VRIL HUD.

This only changes texture presentation; existing role dispatch, ADS/gyro,
press/release timing, joystick logic, HUD editor/hitboxes and weapon handling
stay untouched. Called AFTER mobile_v022 and only for CHURCH_MINI builds.
"""
from pathlib import Path
import sys

if len(sys.argv)!=2:
    raise SystemExit("usage: patch_vril_approved_touch_skins.py <vril-root>")
root=Path(sys.argv[1])
hud=root/"source/render/r_hud.c"
text=hud.read_text(encoding="utf-8")

skins=("fire","ads","adsfire","reload","jump","grenade","knife",
       "slide","swap","sprint","claw","crouch","prone")
anchor="static image_t xziel_touch_idle;\n"
if text.count(anchor)!=1:
    raise RuntimeError("Native modern touch-surface handles were changed")
handles="".join("static image_t xziel_approved_skin_%s;\n"%role for role in skins)
if "xziel_approved_skin_fire" in text:
    raise RuntimeError("Approved native HUD already patched")
text=text.replace(anchor,anchor+handles,1)

load_anchor='    xziel_touch_idle = Image_LoadImage("gfx/xziel/touch_idle", IMAGE_PNG, 0, true, false);\n'
if text.count(load_anchor)!=1:
    raise RuntimeError("Cannot locate native image-loader block")
loads="".join(
    '    xziel_approved_skin_%s = Image_LoadImage("gfx/xziel/skin_%s", IMAGE_PNG, 0, true, false);\n'%(role,role)
    for role in skins)
text=text.replace(load_anchor,load_anchor+loads,1)

function_start="static void Xziel_DrawTouchButton("
if text.count(function_start)!=1:
    raise RuntimeError("Expected one native touch draw method")

lookup=r'''/* These textures are the real approved XZIEL Sep-29 authoring,
   packaged by install_approved_touch_skins.py from the Godot source tree.
   One texture per control: never stack another circle+glyph above it. */
static image_t Xziel_ApprovedControlSkin(const char *label1, const char *label2)
{
    if (!strcmp(label1, "FIRE")) return xziel_approved_skin_fire;
    if (!strcmp(label1, "ADS") && label2 && !strcmp(label2, "FIRE"))
        return xziel_approved_skin_adsfire;
    if (!strcmp(label1, "ADS")) return xziel_approved_skin_ads;
    if (!strcmp(label1, "RLD")) return xziel_approved_skin_reload;
    if (!strcmp(label1, "JUMP")) return xziel_approved_skin_jump;
    if (!strcmp(label1, "KNIFE")) return xziel_approved_skin_knife;
    if (!strcmp(label1, "NADE")) return xziel_approved_skin_grenade;
    if (!strcmp(label1, "SLIDE")) return xziel_approved_skin_slide;
    return 0; /* USE/PAUSE intentionally retain their existing official art. */
}

'''
text=text.replace(function_start,lookup+function_start,1)

start=text.index(function_start)
# The final mobile_v022 renderer sets alpha then decides between editor and
# touch roles. Intercept ONLY normal gameplay; editor keeps visible selection.
draw_anchor='\talpha = (int)(255 * xziel_mobile_hud_opacity.value * local_opacity);\n\n\tif (editor) {'
if text[start:].count(draw_anchor)!=1:
    raise RuntimeError("Native touch drawing changed: refusing loose replacement")
approved=r'''	alpha = (int)(255 * xziel_mobile_hud_opacity.value * local_opacity);

	/* Render the exact author-approved touch button once, no fake circles
	   or a competing generic CC0 glyph over the custom PNG. */
	if (!editor) {
		image_t approved_skin = Xziel_ApprovedControlSkin(label1,label2);
		if (approved_skin) {
			int skin_size = (int)(radius * (pressed ? 2.33f : 2.20f));
			int skin_alpha = (int)((pressed ? 246.0f : 210.0f) *
				xziel_mobile_hud_opacity.value * local_opacity);
			if (skin_size < 18) skin_size = 18;
			if (skin_alpha > 255) skin_alpha = 255;
			if (skin_alpha < 25) skin_alpha = 25;
			Draw_ColoredStretchPic(cx-skin_size/2,cy-skin_size/2,
				approved_skin,skin_size,skin_size,255,255,255,skin_alpha);
			return;
		}
	}

	if (editor) {'''
text=text[:start]+text[start:].replace(draw_anchor,approved,1)
hud.write_text(text,encoding="utf-8")
print("XZIEL_APPROVED_TOUCH_LATEST12_RENDERER_PATCH_GREEN",len(skins))
