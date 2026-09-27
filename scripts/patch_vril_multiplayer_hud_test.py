#!/usr/bin/env python3
"""Xziel multiplayer HUD test pass.

Keeps the existing v0.24 crouch/slide gameplay and presentation. This pass only
simplifies the mobile weapon switch UI for the multiplayer APK:
- one compact SWAP card instead of three independent weapon cards;
- card always represents native weapon slot 1 <-> slot 2;
- one tap uses the already-authoritative impulse 60 rotation;
- legacy third-slot state/protocol remains untouched but is not drawn here.

Applied after patch_vril_mobile_v024.py.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_vril_multiplayer_hud_test.py <vril-root>")

root = Path(sys.argv[1])
source = root / "source"

def replace_function(src: str, signature: str, replacement: str) -> str:
    start = src.find(signature)
    if start < 0:
        raise SystemExit("Could not find function: " + signature)
    brace = src.find("{", start)
    if brace < 0:
        raise SystemExit("Could not find body: " + signature)
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
# Touch hit target.
#
# Runtime code already maps slot 1 to XZ_TOUCH_WEAPON2 -> impulse 60. Editor
# code checks slot 0 first. Make both logical hit slots cover the same single
# compact swap card, while retiring the old visible slot-3 hit target.
# ---------------------------------------------------------------------------
sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sdl.read_text(encoding="utf-8")

weapon_hit = r'''static qboolean Xziel_WeaponStripHit(float x, float y, int slot)
{
	float s = xziel_hud_weapon1_scale.value;
	float cx = xziel_hud_weapon1_x.value;
	float cy = xziel_hud_weapon1_y.value;
	float w = 0.155f;
	float h = 0.084f;

	if (slot == 2)
		return false;
	if (s < 0.35f) s = 0.35f;
	if (s > 2.25f) s = 2.25f;
	return Xziel_PointInRect(x, y, cx, cy, w * s, h * s);
}'''
text = replace_function(
    text,
    "static qboolean Xziel_WeaponStripHit(float x, float y, int slot)",
    weapon_hit,
)
sdl.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# HUD: one swap card. No independent gun cards.
# ---------------------------------------------------------------------------
hud = source / "render" / "r_hud.c"
text = hud.read_text(encoding="utf-8")

swap_strip = r'''static void Xziel_DrawWeaponStrip(qboolean editor)
{
	static int last_active_weapon = -1;
	static double switch_anim_until;
	double now = Sys_FloatTime();
	float pulse = 1.0f;
	float s = xziel_hud_weapon1_scale.value;
	float opacity = xziel_hud_weapon1_opacity.value;
	int active = cl.stats[STAT_ACTIVEWEAPON];
	int secondary = cl.stats[STAT_XZIEL_W2];
	int cx, cy, w, h, x, y, border, alpha, inner_alpha;
	int left_x, right_x, gun_y, arrow_y1, arrow_y2;
	int one_w, two_w;
	const char *one = "1";
	const char *two = "2";
	const char *swap = "SWAP";

	if (!editor && secondary == 0)
		return;

	if (active != last_active_weapon) {
		last_active_weapon = active;
		switch_anim_until = now + 0.18;
	}
	if (switch_anim_until > now) {
		float t = (float)((switch_anim_until - now) / 0.18);
		pulse = 1.0f + 0.065f * t;
	}

	if (s < 0.35f) s = 0.35f;
	if (s > 2.25f) s = 2.25f;
	if (opacity < 0.15f) opacity = 0.15f;
	if (opacity > 1.0f) opacity = 1.0f;
	s *= pulse;

	cx = (int)(xziel_hud_weapon1_x.value * vid.width);
	cy = (int)(xziel_hud_weapon1_y.value * vid.height);
	w = (int)(104.0f * vid.scale * s);
	h = (int)(50.0f * vid.scale * s);
	if (w < 72) w = 72;
	if (h < 34) h = 34;
	x = cx - w/2;
	y = cy - h/2;
	border = (int)fmaxf(2.0f, 2.0f * vid.scale * s);
	alpha = (int)(214 * xziel_mobile_hud_opacity.value * opacity);
	inner_alpha = (int)(190 * xziel_mobile_hud_opacity.value * opacity);

	/* Reference-inspired skin: smoky black interior + unmistakable yellow rim. */
	Draw_FillByColor(x, y, w, h, 3,5,7,alpha);
	Draw_FillByColor(x + border, y + border, w - border*2, h - border*2,
		17,19,20,inner_alpha);
	Draw_FillByColor(x, y, w, border, 238,235,36,245);
	Draw_FillByColor(x, y + h - border, w, border, 238,235,36,245);
	Draw_FillByColor(x, y, border, h, 238,235,36,245);
	Draw_FillByColor(x + w - border, y, border, h, 238,235,36,245);

	left_x = x + (int)(w * 0.27f);
	right_x = x + (int)(w * 0.73f);
	gun_y = y + (int)(h * 0.52f);

	/* Actual native weapon silhouettes, not generic gun cards. */
	if (active != 0)
		Xziel_DrawWeaponGlyph(left_x, gun_y, active,
			h / (52.0f * vid.scale), 250);
	if (secondary != 0)
		Xziel_DrawWeaponGlyph(right_x, gun_y, secondary,
			h / (52.0f * vid.scale), 235);

	/* Slot numbers make 1 <-> 2 obvious even on a quick glance. */
	one_w = getTextWidth((char *)one, vid.scale * 0.62f * s);
	two_w = getTextWidth((char *)two, vid.scale * 0.62f * s);
	Draw_ColoredString(x + (int)(5*vid.scale*s),
		y + (int)(3*vid.scale*s), (char *)one,
		248,244,72,255,vid.scale*0.62f*s);
	Draw_ColoredString(x + w - two_w - (int)(5*vid.scale*s),
		y + (int)(3*vid.scale*s), (char *)two,
		248,244,72,255,vid.scale*0.62f*s);

	/* Two ASCII arrow lanes are deliberately simple and legible on Android. */
	arrow_y1 = y + (int)(h * 0.31f);
	arrow_y2 = y + (int)(h * 0.61f);
	Draw_ColoredString(cx - getTextWidth((char *)">", vid.scale*0.72f*s)/2,
		arrow_y1, ">", 255,255,255,245,vid.scale*0.72f*s);
	Draw_ColoredString(cx - getTextWidth((char *)"<", vid.scale*0.72f*s)/2,
		arrow_y2, "<", 255,255,255,245,vid.scale*0.72f*s);

	if (editor) {
		int sw = getTextWidth((char *)swap, vid.scale*0.42f*s);
		Draw_ColoredString(cx-sw/2, y+h-(int)(10*vid.scale*s),
			(char *)swap, 220,224,228,220,vid.scale*0.42f*s);
	}
}'''
text = replace_function(
    text,
    "static void Xziel_DrawWeaponStrip(qboolean editor)",
    swap_strip,
)

hud.write_text(text, encoding="utf-8")

print("Applied Xziel multiplayer HUD swap-card test pass.")
