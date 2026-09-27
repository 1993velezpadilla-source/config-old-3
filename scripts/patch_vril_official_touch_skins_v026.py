#!/usr/bin/env python3
"""Xziel v0.26: official zombie touch skins + two-weapon mobile controls.

Runs after the existing mobile/HUD patches and intentionally changes only the
Android touch presentation/input layer:
- draw the approved full-button PNG skins directly;
- remove the old weapon-card strip from the mobile HUD;
- restore the existing SWAP action as the only weapon-slot UI;
- add dedicated CROUCH (stock impulse 31) and PRONE (stock impulse 32);
- preserve SLIDE as the existing Xziel impulse 34 action.

The stock NZ:P stance commands remain server authoritative.
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_vril_official_touch_skins_v026.py <vril-source>")

source = Path(sys.argv[1]) / "source"
if not source.is_dir():
    raise SystemExit(f"missing Vril source tree: {source}")


def find_function_end(src: str, signature: str) -> tuple[int, int]:
    start = src.find(signature)
    if start < 0:
        raise SystemExit(f"Could not find function: {signature}")
    brace = src.find("{", start)
    if brace < 0:
        raise SystemExit(f"Could not find function brace: {signature}")
    depth = 0
    for pos in range(brace, len(src)):
        ch = src[pos]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return start, pos + 1
    raise SystemExit(f"Unterminated function: {signature}")


def replace_function(src: str, signature: str, replacement: str) -> str:
    start, end = find_function_end(src, signature)
    return src[:start] + replacement + src[end:]


def add_after(src: str, anchor: str, payload: str, label: str) -> str:
    if payload.strip() in src:
        return src
    if anchor not in src:
        raise SystemExit(f"Missing anchor: {label}")
    return src.replace(anchor, anchor + payload, 1)


# ---------------------------------------------------------------------------
# Persistent positions for the two newly split stance buttons.
# ---------------------------------------------------------------------------
inp = source / "input.c"
text = inp.read_text(encoding="utf-8")

cvar_anchor = 'cvar_t xziel_hud_slide_opacity = {"xziel_hud_slide_opacity", "0.82", true};\n'
cvars = r'''cvar_t xziel_hud_crouch_x = {"xziel_hud_crouch_x", "0.635", true};
cvar_t xziel_hud_crouch_y = {"xziel_hud_crouch_y", "0.875", true};
cvar_t xziel_hud_crouch_scale = {"xziel_hud_crouch_scale", "1.00", true};
cvar_t xziel_hud_crouch_opacity = {"xziel_hud_crouch_opacity", "0.82", true};
cvar_t xziel_hud_prone_x = {"xziel_hud_prone_x", "0.555", true};
cvar_t xziel_hud_prone_y = {"xziel_hud_prone_y", "0.875", true};
cvar_t xziel_hud_prone_scale = {"xziel_hud_prone_scale", "1.00", true};
cvar_t xziel_hud_prone_opacity = {"xziel_hud_prone_opacity", "0.82", true};
cvar_t xziel_hud_switch_scale = {"xziel_hud_switch_scale", "1.00", true};
cvar_t xziel_hud_switch_opacity = {"xziel_hud_switch_opacity", "0.82", true};
'''
if "cvar_t xziel_hud_crouch_x" not in text:
    text = add_after(text, cvar_anchor, cvars, "official stance HUD cvars")

reg_anchor = "\tCvar_RegisterVariable(&xziel_hud_slide_opacity);\n"
regs = r'''	Cvar_RegisterVariable(&xziel_hud_crouch_x);
	Cvar_RegisterVariable(&xziel_hud_crouch_y);
	Cvar_RegisterVariable(&xziel_hud_crouch_scale);
	Cvar_RegisterVariable(&xziel_hud_crouch_opacity);
	Cvar_RegisterVariable(&xziel_hud_prone_x);
	Cvar_RegisterVariable(&xziel_hud_prone_y);
	Cvar_RegisterVariable(&xziel_hud_prone_scale);
	Cvar_RegisterVariable(&xziel_hud_prone_opacity);
	Cvar_RegisterVariable(&xziel_hud_switch_scale);
	Cvar_RegisterVariable(&xziel_hud_switch_opacity);
'''
if "Cvar_RegisterVariable(&xziel_hud_crouch_x);" not in text:
    text = add_after(text, reg_anchor, regs, "official stance HUD cvar registrations")

inp.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# SDL touch runtime: distinct crouch/prone roles + no weapon-card hit targets.
# ---------------------------------------------------------------------------
sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sdl.read_text(encoding="utf-8")

extern_anchor = "extern cvar_t xziel_hud_slide_opacity;\n"
externs = r'''extern cvar_t xziel_hud_crouch_x;
extern cvar_t xziel_hud_crouch_y;
extern cvar_t xziel_hud_crouch_scale;
extern cvar_t xziel_hud_crouch_opacity;
extern cvar_t xziel_hud_prone_x;
extern cvar_t xziel_hud_prone_y;
extern cvar_t xziel_hud_prone_scale;
extern cvar_t xziel_hud_prone_opacity;
extern cvar_t xziel_hud_switch_scale;
extern cvar_t xziel_hud_switch_opacity;
'''
if "extern cvar_t xziel_hud_crouch_x;" not in text:
    text = add_after(text, extern_anchor, externs, "official stance HUD externs")

# Append roles; never renumber any established role used by older patches.
enum_end = "} xziel_touch_role_t;"
if "XZ_TOUCH_CROUCH" not in text or "XZ_TOUCH_PRONE" not in text:
    enum_pos = text.find(enum_end)
    if enum_pos < 0:
        raise SystemExit("Could not find touch role enum")
    before = text[:enum_pos].rstrip()
    if not before.endswith(","):
        before += ","
    text = before + "\n\tXZ_TOUCH_CROUCH,\n\tXZ_TOUCH_PRONE\n" + text[enum_pos:]

state_anchor = "qboolean xziel_mobile_slide_pressed = false;\n"
states = r'''qboolean xziel_mobile_crouch_pressed = false;
qboolean xziel_mobile_prone_pressed = false;
'''
if "xziel_mobile_crouch_pressed" not in text:
    text = add_after(text, state_anchor, states, "official stance pressed state")

role_func = r'''static xziel_touch_role_t Xziel_RoleForPoint(float x, float y)
{
	float hs = xziel_mobile_hud_scale.value;
	if (Xziel_IsInside(x, y, xziel_hud_fire_x.value, xziel_hud_fire_y.value, 0.073f * hs * xziel_hud_fire_scale.value)) return XZ_TOUCH_FIRE;
	if (Xziel_IsInside(x, y, xziel_hud_adsfire_x.value, xziel_hud_adsfire_y.value, 0.056f * hs * xziel_hud_adsfire_scale.value)) return XZ_TOUCH_ADSFIRE;
	if (Xziel_IsInside(x, y, xziel_hud_ads_x.value, xziel_hud_ads_y.value, 0.047f * hs * xziel_hud_ads_scale.value)) return XZ_TOUCH_ADS;
	if (Xziel_IsInside(x, y, xziel_hud_reload_x.value, xziel_hud_reload_y.value, 0.044f * hs * xziel_hud_reload_scale.value)) return XZ_TOUCH_RELOAD;
	if (xziel_mobile_use_available && Xziel_IsInside(x, y, xziel_hud_use_x.value, xziel_hud_use_y.value, 0.050f * hs * xziel_hud_use_scale.value)) return XZ_TOUCH_USE;
	if (Xziel_IsInside(x, y, xziel_hud_pause_x.value, xziel_hud_pause_y.value, 0.036f * hs * xziel_hud_pause_scale.value)) return XZ_TOUCH_PAUSE;
	if (Xziel_IsInside(x, y, xziel_hud_grenade_x.value, xziel_hud_grenade_y.value, 0.041f * hs * xziel_hud_grenade_scale.value)) return XZ_TOUCH_GRENADE;
	if (Xziel_IsInside(x, y, xziel_hud_jump_x.value, xziel_hud_jump_y.value, 0.044f * hs * xziel_hud_jump_scale.value)) return XZ_TOUCH_JUMP;
	if (Xziel_IsInside(x, y, xziel_hud_slide_x.value, xziel_hud_slide_y.value, 0.044f * hs * xziel_hud_slide_scale.value)) return XZ_TOUCH_SLIDE;
	if (Xziel_IsInside(x, y, xziel_hud_crouch_x.value, xziel_hud_crouch_y.value, 0.044f * hs * xziel_hud_crouch_scale.value)) return XZ_TOUCH_CROUCH;
	if (Xziel_IsInside(x, y, xziel_hud_prone_x.value, xziel_hud_prone_y.value, 0.044f * hs * xziel_hud_prone_scale.value)) return XZ_TOUCH_PRONE;
	if ((!xziel_mobile_knife_range_only.value || xziel_mobile_knife_target_near) &&
		Xziel_IsInside(x, y, xziel_hud_knife_x.value, xziel_hud_knife_y.value, 0.044f * hs * xziel_hud_knife_scale.value)) return XZ_TOUCH_KNIFE;
	if (Xziel_IsInside(x, y, xziel_hud_switch_x.value, xziel_hud_switch_y.value, 0.041f * hs * xziel_hud_switch_scale.value)) return XZ_TOUCH_SWITCH;
	if (x < 0.45f && y > 0.30f) return XZ_TOUCH_MOVE;
	return XZ_TOUCH_LOOK;
}'''
text = replace_function(text, "static xziel_touch_role_t Xziel_RoleForPoint(float x, float y)", role_func)

editor_role = r'''static xziel_touch_role_t Xziel_HudEditorRole(float x, float y)
{
	float hs = xziel_mobile_hud_scale.value;
	if (Xziel_IsInside(x, y, xziel_hud_minimap_x.value, xziel_hud_minimap_y.value,
		0.082f * hs * xziel_hud_minimap_scale.value)) return XZ_TOUCH_MINIMAP;
	if (Xziel_IsInside(x, y, xziel_hud_fire_x.value, xziel_hud_fire_y.value, 0.090f * hs * xziel_hud_fire_scale.value)) return XZ_TOUCH_FIRE;
	if (Xziel_IsInside(x, y, xziel_hud_adsfire_x.value, xziel_hud_adsfire_y.value, 0.075f * hs * xziel_hud_adsfire_scale.value)) return XZ_TOUCH_ADSFIRE;
	if (Xziel_IsInside(x, y, xziel_hud_ads_x.value, xziel_hud_ads_y.value, 0.065f * hs * xziel_hud_ads_scale.value)) return XZ_TOUCH_ADS;
	if (Xziel_IsInside(x, y, xziel_hud_reload_x.value, xziel_hud_reload_y.value, 0.060f * hs * xziel_hud_reload_scale.value)) return XZ_TOUCH_RELOAD;
	if (Xziel_IsInside(x, y, xziel_hud_use_x.value, xziel_hud_use_y.value, 0.065f * hs * xziel_hud_use_scale.value)) return XZ_TOUCH_USE;
	if (Xziel_IsInside(x, y, xziel_hud_pause_x.value, xziel_hud_pause_y.value, 0.055f * hs * xziel_hud_pause_scale.value)) return XZ_TOUCH_PAUSE;
	if (Xziel_IsInside(x, y, xziel_hud_grenade_x.value, xziel_hud_grenade_y.value, 0.057f * hs * xziel_hud_grenade_scale.value)) return XZ_TOUCH_GRENADE;
	if (Xziel_IsInside(x, y, xziel_hud_slide_x.value, xziel_hud_slide_y.value, 0.060f * hs * xziel_hud_slide_scale.value)) return XZ_TOUCH_SLIDE;
	if (Xziel_IsInside(x, y, xziel_hud_crouch_x.value, xziel_hud_crouch_y.value, 0.060f * hs * xziel_hud_crouch_scale.value)) return XZ_TOUCH_CROUCH;
	if (Xziel_IsInside(x, y, xziel_hud_prone_x.value, xziel_hud_prone_y.value, 0.060f * hs * xziel_hud_prone_scale.value)) return XZ_TOUCH_PRONE;
	if (Xziel_IsInside(x, y, xziel_hud_jump_x.value, xziel_hud_jump_y.value, 0.060f * hs * xziel_hud_jump_scale.value)) return XZ_TOUCH_JUMP;
	if (Xziel_IsInside(x, y, xziel_hud_knife_x.value, xziel_hud_knife_y.value, 0.060f * hs * xziel_hud_knife_scale.value)) return XZ_TOUCH_KNIFE;
	if (Xziel_IsInside(x, y, xziel_hud_switch_x.value, xziel_hud_switch_y.value, 0.057f * hs * xziel_hud_switch_scale.value)) return XZ_TOUCH_SWITCH;
	if (Xziel_IsInside(x, y, xziel_hud_joy_x.value, xziel_hud_joy_y.value, 0.120f * hs * xziel_hud_joy_scale.value)) return XZ_TOUCH_MOVE;
	return XZ_TOUCH_NONE;
}'''
text = replace_function(text, "static xziel_touch_role_t Xziel_HudEditorRole(float x, float y)", editor_role)

editor_set = r'''static void Xziel_HudEditorSetPosition(xziel_touch_role_t role, float x, float y)
{
	if (x < 0.035f) x = 0.035f;
	if (x > 0.965f) x = 0.965f;
	if (y < 0.055f) y = 0.055f;
	if (y > 0.945f) y = 0.945f;
	xziel_hud_editor_selected = role;
	switch (role) {
	case XZ_TOUCH_MOVE: Cvar_SetValue("xziel_hud_joy_x", x); Cvar_SetValue("xziel_hud_joy_y", y); break;
	case XZ_TOUCH_FIRE: Cvar_SetValue("xziel_hud_fire_x", x); Cvar_SetValue("xziel_hud_fire_y", y); break;
	case XZ_TOUCH_ADSFIRE: Cvar_SetValue("xziel_hud_adsfire_x", x); Cvar_SetValue("xziel_hud_adsfire_y", y); break;
	case XZ_TOUCH_ADS: Cvar_SetValue("xziel_hud_ads_x", x); Cvar_SetValue("xziel_hud_ads_y", y); break;
	case XZ_TOUCH_RELOAD: Cvar_SetValue("xziel_hud_reload_x", x); Cvar_SetValue("xziel_hud_reload_y", y); break;
	case XZ_TOUCH_USE: Cvar_SetValue("xziel_hud_use_x", x); Cvar_SetValue("xziel_hud_use_y", y); break;
	case XZ_TOUCH_JUMP: Cvar_SetValue("xziel_hud_jump_x", x); Cvar_SetValue("xziel_hud_jump_y", y); break;
	case XZ_TOUCH_SLIDE: Cvar_SetValue("xziel_hud_slide_x", x); Cvar_SetValue("xziel_hud_slide_y", y); break;
	case XZ_TOUCH_CROUCH: Cvar_SetValue("xziel_hud_crouch_x", x); Cvar_SetValue("xziel_hud_crouch_y", y); break;
	case XZ_TOUCH_PRONE: Cvar_SetValue("xziel_hud_prone_x", x); Cvar_SetValue("xziel_hud_prone_y", y); break;
	case XZ_TOUCH_KNIFE: Cvar_SetValue("xziel_hud_knife_x", x); Cvar_SetValue("xziel_hud_knife_y", y); break;
	case XZ_TOUCH_GRENADE: Cvar_SetValue("xziel_hud_grenade_x", x); Cvar_SetValue("xziel_hud_grenade_y", y); break;
	case XZ_TOUCH_SWITCH: Cvar_SetValue("xziel_hud_switch_x", x); Cvar_SetValue("xziel_hud_switch_y", y); break;
	case XZ_TOUCH_PAUSE: Cvar_SetValue("xziel_hud_pause_x", x); Cvar_SetValue("xziel_hud_pause_y", y); break;
	case XZ_TOUCH_MINIMAP: Cvar_SetValue("xziel_hud_minimap_x", x); Cvar_SetValue("xziel_hud_minimap_y", y); break;
	default: break;
	}
}'''
text = replace_function(text, "static void Xziel_HudEditorSetPosition(xziel_touch_role_t role, float x, float y)", editor_set)

# Dedicated stance actions use stock NZ:P server-authoritative impulses.
d0, d1 = find_function_end(text, "static void Xziel_ActionDown(xziel_touch_role_t role)")
down = text[d0:d1]
if "case XZ_TOUCH_CROUCH:" not in down:
    anchor = "\tcase XZ_TOUCH_JUMP:\n"
    payload = r'''	case XZ_TOUCH_CROUCH:
		xziel_mobile_crouch_pressed = true;
		Cbuf_AddText("impulse 31\n");
		break;
	case XZ_TOUCH_PRONE:
		xziel_mobile_prone_pressed = true;
		Cbuf_AddText("impulse 32\n");
		break;
'''
    if anchor not in down:
        raise SystemExit("Could not find ActionDown jump anchor")
    down = down.replace(anchor, payload + anchor, 1)
    text = text[:d0] + down + text[d1:]

u0, u1 = find_function_end(text, "static void Xziel_ActionUp(xziel_touch_role_t role)")
up = text[u0:u1]
if "case XZ_TOUCH_CROUCH:" not in up:
    anchor = "\tcase XZ_TOUCH_JUMP:\n"
    payload = r'''	case XZ_TOUCH_CROUCH:
		xziel_mobile_crouch_pressed = false;
		break;
	case XZ_TOUCH_PRONE:
		xziel_mobile_prone_pressed = false;
		break;
'''
    if anchor not in up:
        raise SystemExit("Could not find ActionUp jump anchor")
    up = up.replace(anchor, payload + anchor, 1)
    text = text[:u0] + up + text[u1:]

sdl.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# HUD: draw approved PNGs as the complete button face; no weapon cards.
# ---------------------------------------------------------------------------
hud = source / "render" / "r_hud.c"
text = hud.read_text(encoding="utf-8")

hud_extern_anchor = "extern cvar_t xziel_hud_slide_opacity;\n"
hud_externs = r'''extern cvar_t xziel_hud_crouch_x;
extern cvar_t xziel_hud_crouch_y;
extern cvar_t xziel_hud_crouch_scale;
extern cvar_t xziel_hud_crouch_opacity;
extern cvar_t xziel_hud_prone_x;
extern cvar_t xziel_hud_prone_y;
extern cvar_t xziel_hud_prone_scale;
extern cvar_t xziel_hud_prone_opacity;
extern cvar_t xziel_hud_switch_scale;
extern cvar_t xziel_hud_switch_opacity;
extern qboolean xziel_mobile_crouch_pressed;
extern qboolean xziel_mobile_prone_pressed;
'''
if "extern cvar_t xziel_hud_crouch_x;" not in text:
    text = add_after(text, hud_extern_anchor, hud_externs, "official HUD stance externs")

handle_anchor = "static image_t xziel_icon_slide;\n"
handles = r'''static image_t xziel_icon_switch;
static image_t xziel_icon_crouch;
static image_t xziel_icon_prone;
'''
if "static image_t xziel_icon_switch;" not in text:
    text = add_after(text, handle_anchor, handles, "official HUD image handles")

load_anchor = '    xziel_icon_slide   = Image_LoadImage("gfx/xziel/slide", IMAGE_PNG, 0, true, false);\n'
loads = r'''    xziel_icon_switch  = Image_LoadImage("gfx/xziel/switch", IMAGE_PNG, 0, true, false);
    xziel_icon_crouch  = Image_LoadImage("gfx/xziel/crouch", IMAGE_PNG, 0, true, false);
    xziel_icon_prone   = Image_LoadImage("gfx/xziel/prone", IMAGE_PNG, 0, true, false);
'''
if 'gfx/xziel/crouch' not in text:
    text = add_after(text, load_anchor, loads, "official HUD image loads")

control_style = r'''static void Xziel_ControlStyle(const char *label1, const char *label2, float *scale, float *opacity)
{
	*scale = 1.0f; *opacity = 1.0f;
	if (!strcmp(label1, "FIRE")) { *scale = xziel_hud_fire_scale.value; *opacity = xziel_hud_fire_opacity.value; }
	else if (!strcmp(label1, "ADS") && label2 && !strcmp(label2, "FIRE")) { *scale = xziel_hud_adsfire_scale.value; *opacity = xziel_hud_adsfire_opacity.value; }
	else if (!strcmp(label1, "ADS")) { *scale = xziel_hud_ads_scale.value; *opacity = xziel_hud_ads_opacity.value; }
	else if (!strcmp(label1, "RLD")) { *scale = xziel_hud_reload_scale.value; *opacity = xziel_hud_reload_opacity.value; }
	else if (!strcmp(label1, "USE")) { *scale = xziel_hud_use_scale.value; *opacity = xziel_hud_use_opacity.value; }
	else if (!strcmp(label1, "JUMP")) { *scale = xziel_hud_jump_scale.value; *opacity = xziel_hud_jump_opacity.value; }
	else if (!strcmp(label1, "KNIFE")) { *scale = xziel_hud_knife_scale.value; *opacity = xziel_hud_knife_opacity.value; }
	else if (!strcmp(label1, "NADE")) { *scale = xziel_hud_grenade_scale.value; *opacity = xziel_hud_grenade_opacity.value; }
	else if (!strcmp(label1, "SLIDE")) { *scale = xziel_hud_slide_scale.value; *opacity = xziel_hud_slide_opacity.value; }
	else if (!strcmp(label1, "CROUCH")) { *scale = xziel_hud_crouch_scale.value; *opacity = xziel_hud_crouch_opacity.value; }
	else if (!strcmp(label1, "PRONE")) { *scale = xziel_hud_prone_scale.value; *opacity = xziel_hud_prone_opacity.value; }
	else if (!strcmp(label1, "SWAP")) { *scale = xziel_hud_switch_scale.value; *opacity = xziel_hud_switch_opacity.value; }
	else if (!strcmp(label1, "II")) { *scale = xziel_hud_pause_scale.value; *opacity = xziel_hud_pause_opacity.value; }
	if (*scale < 0.20f) *scale = 0.20f;
	if (*scale > 4.00f) *scale = 4.00f;
	if (*opacity < 0.15f) *opacity = 0.15f;
	if (*opacity > 1.00f) *opacity = 1.00f;
}'''
text = replace_function(text, "static void Xziel_ControlStyle", control_style)

action_icon = r'''static image_t Xziel_ActionIcon(const char *label1, const char *label2)
{
	if (!strcmp(label1, "ADS") && label2 && !strcmp(label2, "FIRE")) return xziel_icon_adsfire;
	if (!strcmp(label1, "FIRE")) return xziel_icon_fire;
	if (!strcmp(label1, "ADS")) return xziel_icon_ads;
	if (!strcmp(label1, "RLD")) return xziel_icon_reload;
	if (!strcmp(label1, "USE")) return xziel_icon_use;
	if (!strcmp(label1, "JUMP")) return xziel_icon_jump;
	if (!strcmp(label1, "KNIFE")) return xziel_icon_knife;
	if (!strcmp(label1, "NADE")) return xziel_icon_grenade;
	if (!strcmp(label1, "SLIDE")) return xziel_icon_slide;
	if (!strcmp(label1, "CROUCH")) return xziel_icon_crouch;
	if (!strcmp(label1, "PRONE")) return xziel_icon_prone;
	if (!strcmp(label1, "SWAP")) return xziel_icon_switch;
	if (!strcmp(label1, "II")) return xziel_icon_pause;
	return 0;
}'''
text = replace_function(text, "static image_t Xziel_ActionIcon", action_icon)

official_helper = r'''
static qboolean Xziel_IsOfficialFullButton(const char *label1, const char *label2)
{
	if (!strcmp(label1, "ADS") && label2 && !strcmp(label2, "FIRE")) return true;
	return !strcmp(label1, "FIRE") || !strcmp(label1, "ADS") ||
		!strcmp(label1, "RLD") || !strcmp(label1, "USE") ||
		!strcmp(label1, "JUMP") || !strcmp(label1, "KNIFE") ||
		!strcmp(label1, "NADE") || !strcmp(label1, "SLIDE") ||
		!strcmp(label1, "CROUCH") || !strcmp(label1, "PRONE") ||
		!strcmp(label1, "SWAP");
}
'''
if "static qboolean Xziel_IsOfficialFullButton" not in text:
    icon_end = find_function_end(text, "static image_t Xziel_ActionIcon")[1]
    text = text[:icon_end] + "\n" + official_helper + text[icon_end:]

touch = r'''static void Xziel_DrawTouchButton(float nx, float ny, float radius_h,
	const char *label1, const char *label2, qboolean pressed, qboolean editor)
{
	float local_scale, local_opacity;
	int cx = (int)(nx * vid.width);
	int cy = (int)(ny * vid.height);
	int radius;
	int size;
	int alpha;
	image_t surface = 0;
	image_t official = 0;

	Xziel_ControlStyle(label1, label2, &local_scale, &local_opacity);
	if (local_scale < 0.20f) local_scale = 0.20f;
	if (local_scale > 4.00f) local_scale = 4.00f;
	if (local_opacity < 0.15f) local_opacity = 0.15f;
	if (local_opacity > 1.00f) local_opacity = 1.00f;

	radius = (int)(radius_h * vid.height *
		xziel_mobile_hud_scale.value * local_scale);
	if (radius < 9) radius = 9;
	alpha = (int)(255 * xziel_mobile_hud_opacity.value * local_opacity);

	if (Xziel_IsOfficialFullButton(label1, label2)) {
		official = Xziel_ActionIcon(label1, label2);
		if (official) {
			int gx = cx, gy = cy;
			float press_scale = pressed ? 1.06f : 1.0f;
			size = (int)(radius * 2.20f * press_scale);
			if (!strcmp(label1, "FIRE") && pressed && xziel_mobile_track_fire.value >= 0.5f) {
				gx += (int)(xziel_mobile_track_fire_dx * radius * 0.58f);
				gy += (int)(xziel_mobile_track_fire_dy * radius * 0.58f);
			} else if (!strcmp(label1, "ADS") && label2 && !strcmp(label2, "FIRE") &&
				pressed && xziel_mobile_track_fire.value >= 0.5f) {
				gx += (int)(xziel_mobile_track_adsfire_dx * radius * 0.58f);
				gy += (int)(xziel_mobile_track_adsfire_dy * radius * 0.58f);
			}
			Draw_ColoredStretchPic(gx-size/2, gy-size/2, official,
				size, size, 255,255,255, editor ? 255 : alpha);
			return;
		}
	}

	/* Pause keeps the established generic surface because it is not part of
	   the approved twelve-button art set. */
	size = (int)(radius * 2.14f);
	if (editor)
		surface = xziel_touch_editor;
	else
		surface = pressed ? xziel_touch_small_pressed : xziel_touch_small_idle;
	if (surface)
		Draw_ColoredStretchPic(cx-size/2, cy-size/2, surface,
			size,size,255,255,255,alpha);
	Xziel_DrawActionGlyph(cx,cy,radius,label1,label2,pressed);
}'''
text = replace_function(text, "static void Xziel_DrawTouchButton(", touch)

# Weapon cards are intentionally disabled for this Quake mobile HUD. The
# underlying two-slot weapon system is untouched; SWAP remains the one control.
weapon_strip = r'''static void Xziel_DrawWeaponStrip(qboolean editor)
{
	(void)editor;
}'''
text = replace_function(text, "static void Xziel_DrawWeaponStrip(qboolean editor)", weapon_strip)

# Add the three controls the v0.23 presentation stopped drawing.
m0, m1 = find_function_end(text, "static void Xziel_MobileHUD_DrawInternal(qboolean editor)")
mobile = text[m0:m1]
if '"SWAP"' not in mobile:
    anchor = "\n\tXziel_DrawWeaponStrip(editor);"
    extra = r'''
	Xziel_DrawTouchButton(xziel_hud_switch_x.value, xziel_hud_switch_y.value,
		0.041f, "SWAP", "", xziel_mobile_switch_pressed, editor);
	Xziel_DrawTouchButton(xziel_hud_crouch_x.value, xziel_hud_crouch_y.value,
		0.044f, "CROUCH", "", xziel_mobile_crouch_pressed, editor);
	Xziel_DrawTouchButton(xziel_hud_prone_x.value, xziel_hud_prone_y.value,
		0.044f, "PRONE", "", xziel_mobile_prone_pressed, editor);
'''
    if anchor not in mobile:
        raise SystemExit("Could not find final weapon-strip draw anchor")
    mobile = mobile.replace(anchor, extra + anchor, 1)
    text = text[:m0] + mobile + text[m1:]

hud.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Custom HUD editor: role 10 is SWAP, not FIRE. Give SWAP/crouch/prone their
# own scale/opacity controls and use the requested HIP FIRE label.
# ---------------------------------------------------------------------------
controls = source / "menu" / "menu_controls.c"
text = controls.read_text(encoding="utf-8")

menu_extern_anchor = "extern int xziel_hud_editor_selected;\n"
menu_externs = r'''extern cvar_t xziel_hud_switch_scale;
extern cvar_t xziel_hud_switch_opacity;
extern cvar_t xziel_hud_crouch_scale;
extern cvar_t xziel_hud_crouch_opacity;
extern cvar_t xziel_hud_prone_scale;
extern cvar_t xziel_hud_prone_opacity;
'''
if "extern cvar_t xziel_hud_switch_scale;" not in text:
    text = add_after(text, menu_extern_anchor, menu_externs, "official HUD editor externs")

e0, e1 = find_function_end(text, "void Menu_HudEdit_Draw(void)")
editor = text[e0:e1]
editor = editor.replace('case 3: name="FIRE"; break;', 'case 3: name="HIP FIRE"; break;')
editor = editor.replace('case 16: name="CROUCH / SLIDE"; break;', 'case 16: name="SLIDE"; break;')
if 'case 10: name="WEAPON SWAP"; break;' not in editor:
    editor = editor.replace(
        'case 9: name="KNIFE"; break;\n',
        'case 9: name="KNIFE"; break;\n\tcase 10: name="WEAPON SWAP"; break;\n',
        1
    )
if 'case 18: name="CROUCH"; break;' not in editor:
    editor = editor.replace(
        'case 17: name="MINIMAP"; break;\n',
        'case 17: name="MINIMAP"; break;\n\tcase 18: name="CROUCH"; break;\n\tcase 19: name="PRONE"; break;\n',
        1
    )
if 'case 10: DRAW_STYLE(xziel_hud_switch_scale' not in editor:
    editor = editor.replace(
        'case 9: DRAW_STYLE(xziel_hud_knife_scale, xziel_hud_knife_opacity); break;\n',
        'case 9: DRAW_STYLE(xziel_hud_knife_scale, xziel_hud_knife_opacity); break;\n'
        '\tcase 10: DRAW_STYLE(xziel_hud_switch_scale, xziel_hud_switch_opacity); break;\n',
        1
    )
editor = editor.replace(
    'case 16: DRAW_STYLE(xziel_hud_slide_scale, xziel_hud_slide_opacity); break;\n',
    'case 16: DRAW_STYLE(xziel_hud_slide_scale, xziel_hud_slide_opacity); break;\n'
    '\tcase 18: DRAW_STYLE(xziel_hud_crouch_scale, xziel_hud_crouch_opacity); break;\n'
    '\tcase 19: DRAW_STYLE(xziel_hud_prone_scale, xziel_hud_prone_opacity); break;\n',
    1
)
text = text[:e0] + editor + text[e1:]

r0, r1 = find_function_end(text, "static void Menu_HudEdit_Reset(void)")
reset = text[r0:r1]
reset_anchor = '\tCvar_SetValue("xziel_hud_slide_scale", 1.0f); Cvar_SetValue("xziel_hud_slide_opacity", 0.82f);\n'
reset_payload = reset_anchor + (
    '\tCvar_SetValue("xziel_hud_crouch_scale", 1.0f); Cvar_SetValue("xziel_hud_crouch_opacity", 0.82f);\n'
    '\tCvar_SetValue("xziel_hud_prone_scale", 1.0f); Cvar_SetValue("xziel_hud_prone_opacity", 0.82f);\n'
    '\tCvar_SetValue("xziel_hud_switch_scale", 1.0f); Cvar_SetValue("xziel_hud_switch_opacity", 0.82f);\n'
)
if 'xziel_hud_switch_scale' not in reset:
    if reset_anchor not in reset:
        raise SystemExit("Could not find final HUD editor reset style anchor")
    reset = reset.replace(reset_anchor, reset_payload, 1)
    text = text[:r0] + reset + text[r1:]

controls.write_text(text, encoding="utf-8")

print("Applied Xziel v0.26 official touch skins, dedicated crouch/prone and SWAP-only weapon UI.")
