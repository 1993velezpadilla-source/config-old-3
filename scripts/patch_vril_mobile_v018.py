#!/usr/bin/env python3
"""Xziel Android v0.18 polish.

Applied after patch_vril_android.py and patch_vril_weaponhud.py.

Goals:
- fix Custom HUD Reset/Done touch interception;
- let every touch control carry its own scale and opacity;
- split the three weapon HUD cards into independent editor objects;
- replace hand-drawn touch/weapon glyphs with bundled CC0 assets;
- expose COD-Mobile-style relevant sensitivity groups;
- raise the START ROUND UI ceiling from 50 to the byte-safe 255;
- fix two real Vril waypoint/A* cost bugs found during the pathfinding audit.
"""

from pathlib import Path
import sys


if len(sys.argv) != 2:
    raise SystemExit("usage: patch_vril_mobile_v018.py <vril-root>")

root = Path(sys.argv[1])
source = root / "source"


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


def must_replace(src: str, old: str, new: str, label: str, count: int = 1) -> str:
    if old not in src:
        raise SystemExit("Could not find anchor: " + label)
    return src.replace(old, new, count)


# ---------------------------------------------------------------------------
# START ROUND: the old 50 value is a menu ceiling, not a gameplay round stop.
# Vril serializes current rounds as a byte in legacy protocol paths, so 255 is
# the conservative ceiling until Xziel deliberately extends that protocol.
# ---------------------------------------------------------------------------
gamesettings = source / "menu" / "menu_gamesettings.c"
gtext = gamesettings.read_text(encoding="utf-8")
gtext = gtext.replace(
    'Menu_DrawOptionSlider(3, 2, 0, 50, sv_startround, "sv_startround", true, true, 5.0f);',
    'Menu_DrawOptionSlider(3, 2, 0, 255, sv_startround, "sv_startround", true, true, 5.0f);',
)
gamesettings.write_text(gtext, encoding="utf-8")


# ---------------------------------------------------------------------------
# Waypoint/path audit fixes.
#
# 1. Edge costs were accidentally computed against waypoint 0 via
#    waypoints[s] where s was permanently zero. Use the actual edge target.
# 2. A* g-scores use Euclidean edge lengths but the heuristic used squared
#    distance. That overestimates and can produce non-optimal paths. Use the
#    same Euclidean metric for an admissible heuristic.
# 3. qsort comparator previously returned a float difference as int.
# ---------------------------------------------------------------------------
sv_main = source / "sv_main.c"
stext = sv_main.read_text(encoding="utf-8")
bad_dist = "float dist = VecLength2(waypoints[s].origin, waypoints[i].origin);"
good_dist = (
    "int target_idx = waypoints[i].target[p];\n"
    "\t\t\tfloat dist = VecLength2(waypoints[target_idx].origin, waypoints[i].origin);"
)
if bad_dist not in stext:
    raise SystemExit("Could not find waypoint edge-distance bug anchor")
stext = stext.replace(bad_dist, good_dist)

old_cmp = """int argsort_comparator(const void *lhs, const void *rhs) {
\treturn ((argsort_entry_t*)lhs)->value - ((argsort_entry_t*)rhs)->value;
}"""
new_cmp = """int argsort_comparator(const void *lhs, const void *rhs) {
\tfloat a = ((const argsort_entry_t*)lhs)->value;
\tfloat b = ((const argsort_entry_t*)rhs)->value;
\treturn (a > b) - (a < b);
}"""
if old_cmp in stext:
    stext = stext.replace(old_cmp, new_cmp, 1)
sv_main.write_text(stext, encoding="utf-8")

pr_cmds = source / "qcvm" / "pr_cmds.c"
ptext = pr_cmds.read_text(encoding="utf-8")
heuristic = r'''float sv_way_heuristic_cost_estimate(int waypoint_idx_a, int waypoint_idx_b) {
	return VecLength2(waypoints[waypoint_idx_a].origin, waypoints[waypoint_idx_b].origin);
}'''
ptext = replace_function(
    ptext,
    "float sv_way_heuristic_cost_estimate(int waypoint_idx_a, int waypoint_idx_b)",
    heuristic,
)
pr_cmds.write_text(ptext, encoding="utf-8")


# ---------------------------------------------------------------------------
# Per-control scale/opacity + relevant mobile sensitivity cvars.
# ---------------------------------------------------------------------------
inp = source / "input.c"
itext = inp.read_text(encoding="utf-8")

sens_anchor = 'cvar_t xziel_mobile_ads_sensitivity = {"xziel_mobile_ads_sensitivity", "0.62", true};\n'
sens_defs = r'''cvar_t xziel_mobile_fire_sensitivity = {"xziel_mobile_fire_sensitivity", "1.00", true};
cvar_t xziel_mobile_ads_fire_sensitivity = {"xziel_mobile_ads_fire_sensitivity", "0.62", true};
cvar_t xziel_mobile_sniper_sensitivity = {"xziel_mobile_sniper_sensitivity", "0.42", true};
cvar_t xziel_mobile_sniper_fire_sensitivity = {"xziel_mobile_sniper_fire_sensitivity", "0.42", true};
cvar_t xziel_mobile_gyro_ads_mult = {"xziel_mobile_gyro_ads_mult", "0.65", true};
cvar_t xziel_mobile_gyro_sniper_mult = {"xziel_mobile_gyro_sniper_mult", "0.42", true};
'''
if "xziel_mobile_fire_sensitivity" not in itext:
    itext = must_replace(itext, sens_anchor, sens_anchor + sens_defs, "mobile sensitivity declarations")

control_defaults = {
    "joy": ("1.00", "0.78"),
    "fire": ("1.00", "0.82"),
    "adsfire": ("1.00", "0.82"),
    "ads": ("1.00", "0.82"),
    "reload": ("1.00", "0.82"),
    "use": ("1.00", "0.82"),
    "jump": ("1.00", "0.82"),
    "knife": ("1.00", "0.82"),
    "pause": ("1.00", "0.82"),
    "grenade": ("1.00", "0.82"),
}
style_defs = []
for name, (scale, opacity) in control_defaults.items():
    style_defs.append(f'cvar_t xziel_hud_{name}_scale = {{"xziel_hud_{name}_scale", "{scale}", true}};')
    style_defs.append(f'cvar_t xziel_hud_{name}_opacity = {{"xziel_hud_{name}_opacity", "{opacity}", true}};')

style_defs.extend([
    'cvar_t xziel_hud_weapon1_x = {"xziel_hud_weapon1_x", "0.430", true};',
    'cvar_t xziel_hud_weapon1_y = {"xziel_hud_weapon1_y", "0.885", true};',
    'cvar_t xziel_hud_weapon1_scale = {"xziel_hud_weapon1_scale", "1.00", true};',
    'cvar_t xziel_hud_weapon1_opacity = {"xziel_hud_weapon1_opacity", "0.90", true};',
    'cvar_t xziel_hud_weapon2_x = {"xziel_hud_weapon2_x", "0.555", true};',
    'cvar_t xziel_hud_weapon2_y = {"xziel_hud_weapon2_y", "0.885", true};',
    'cvar_t xziel_hud_weapon2_scale = {"xziel_hud_weapon2_scale", "0.95", true};',
    'cvar_t xziel_hud_weapon2_opacity = {"xziel_hud_weapon2_opacity", "0.82", true};',
    'cvar_t xziel_hud_pistol_x = {"xziel_hud_pistol_x", "0.670", true};',
    'cvar_t xziel_hud_pistol_y = {"xziel_hud_pistol_y", "0.885", true};',
    'cvar_t xziel_hud_pistol_scale = {"xziel_hud_pistol_scale", "0.92", true};',
    'cvar_t xziel_hud_pistol_opacity = {"xziel_hud_pistol_opacity", "0.82", true};',
])
style_block = "\n".join(style_defs) + "\n"
style_anchor = 'cvar_t xziel_hud_grenade_y = {"xziel_hud_grenade_y", "0.300", true};\n'
if "xziel_hud_fire_scale" not in itext:
    itext = must_replace(itext, style_anchor, style_anchor + style_block, "per-control style declarations")

sens_reg_anchor = "\tCvar_RegisterVariable(&xziel_mobile_ads_sensitivity);\n"
sens_regs = """\tCvar_RegisterVariable(&xziel_mobile_fire_sensitivity);
\tCvar_RegisterVariable(&xziel_mobile_ads_fire_sensitivity);
\tCvar_RegisterVariable(&xziel_mobile_sniper_sensitivity);
\tCvar_RegisterVariable(&xziel_mobile_sniper_fire_sensitivity);
\tCvar_RegisterVariable(&xziel_mobile_gyro_ads_mult);
\tCvar_RegisterVariable(&xziel_mobile_gyro_sniper_mult);
"""
if "Cvar_RegisterVariable(&xziel_mobile_fire_sensitivity);" not in itext:
    itext = must_replace(itext, sens_reg_anchor, sens_reg_anchor + sens_regs, "mobile sensitivity registration")

style_regs = []
for name in control_defaults:
    style_regs.append(f"\tCvar_RegisterVariable(&xziel_hud_{name}_scale);")
    style_regs.append(f"\tCvar_RegisterVariable(&xziel_hud_{name}_opacity);")
for name in ("weapon1_x", "weapon1_y", "weapon1_scale", "weapon1_opacity",
             "weapon2_x", "weapon2_y", "weapon2_scale", "weapon2_opacity",
             "pistol_x", "pistol_y", "pistol_scale", "pistol_opacity"):
    style_regs.append(f"\tCvar_RegisterVariable(&xziel_hud_{name});")
style_reg_block = "\n".join(style_regs) + "\n"

style_reg_anchor = "\tCvar_RegisterVariable(&xziel_hud_grenade_y);\n"
if "Cvar_RegisterVariable(&xziel_hud_fire_scale);" not in itext:
    itext = must_replace(itext, style_reg_anchor, style_reg_anchor + style_reg_block, "per-control style registration")

gyro_anchor = """#ifdef __ANDROID__
\t\t\tgyro_scale *= xziel_mobile_gyro_boost.value;
#endif
"""
gyro_repl = """#ifdef __ANDROID__
\t\t\tgyro_scale *= xziel_mobile_gyro_boost.value;
\t\t\tif (cl.stats[STAT_ZOOM] == 2)
\t\t\t\tgyro_scale *= xziel_mobile_gyro_sniper_mult.value;
\t\t\telse if (cl.stats[STAT_ZOOM] == 1)
\t\t\t\tgyro_scale *= xziel_mobile_gyro_ads_mult.value;
#endif
"""
if "xziel_mobile_gyro_sniper_mult.value" not in itext:
    itext = must_replace(itext, gyro_anchor, gyro_repl, "gyro state multipliers")

inp.write_text(itext, encoding="utf-8")


# ---------------------------------------------------------------------------
# Touch runtime: scaled hit regions, separate weapon cards, editor selection,
# correct menu priority, and sensitivity split.
# ---------------------------------------------------------------------------
sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sdl.read_text(encoding="utf-8")

extern_anchor = "extern cvar_t xziel_hud_grenade_y;\n"
extern_lines = [
    "extern cvar_t xziel_mobile_fire_sensitivity;",
    "extern cvar_t xziel_mobile_ads_fire_sensitivity;",
    "extern cvar_t xziel_mobile_sniper_sensitivity;",
    "extern cvar_t xziel_mobile_sniper_fire_sensitivity;",
]
for name in control_defaults:
    extern_lines += [
        f"extern cvar_t xziel_hud_{name}_scale;",
        f"extern cvar_t xziel_hud_{name}_opacity;",
    ]
for name in ("weapon1_x", "weapon1_y", "weapon1_scale", "weapon1_opacity",
             "weapon2_x", "weapon2_y", "weapon2_scale", "weapon2_opacity",
             "pistol_x", "pistol_y", "pistol_scale", "pistol_opacity"):
    extern_lines.append(f"extern cvar_t xziel_hud_{name};")
extern_block = "\n".join(extern_lines) + "\n"
if "extern cvar_t xziel_hud_fire_scale;" not in text:
    text = must_replace(text, extern_anchor, extern_anchor + extern_block, "SDL v0.18 externs")

state_anchor = "static int xziel_menu_confirm_state = -1;\n"
if "int xziel_hud_editor_selected" not in text:
    text = must_replace(
        text,
        state_anchor,
        state_anchor + "int xziel_hud_editor_selected = XZ_TOUCH_FIRE;\n",
        "HUD editor selected state",
    )

weapon_hit = r'''static qboolean Xziel_WeaponStripHit(float x, float y, int slot)
{
	float cx, cy, s, w, h;
	if (slot == 0) {
		cx = xziel_hud_weapon1_x.value; cy = xziel_hud_weapon1_y.value;
		s = xziel_hud_weapon1_scale.value; w = 0.150f; h = 0.100f;
	} else if (slot == 1) {
		cx = xziel_hud_weapon2_x.value; cy = xziel_hud_weapon2_y.value;
		s = xziel_hud_weapon2_scale.value; w = 0.120f; h = 0.085f;
	} else {
		cx = xziel_hud_pistol_x.value; cy = xziel_hud_pistol_y.value;
		s = xziel_hud_pistol_scale.value; w = 0.115f; h = 0.085f;
	}
	if (s < 0.55f) s = 0.55f;
	if (s > 1.80f) s = 1.80f;
	return Xziel_PointInRect(x, y, cx, cy, w * s, h * s);
}'''
text = replace_function(text, "static qboolean Xziel_WeaponStripHit(float x, float y, int slot)", weapon_hit)

group_hit = r'''static qboolean Xziel_WeaponStripGroupHit(float x, float y)
{
	return Xziel_WeaponStripHit(x, y, 0) ||
		Xziel_WeaponStripHit(x, y, 1) ||
		Xziel_WeaponStripHit(x, y, 2);
}'''
text = replace_function(text, "static qboolean Xziel_WeaponStripGroupHit(float x, float y)", group_hit)

role_func = r'''static xziel_touch_role_t Xziel_RoleForPoint(float x, float y)
{
	float hs = xziel_mobile_hud_scale.value;
	if (cl.stats[STAT_XZIEL_W2] != 0 && Xziel_WeaponStripHit(x, y, 1)) return XZ_TOUCH_WEAPON2;
	if (cl.stats[STAT_XZIEL_W3] != 0 && Xziel_WeaponStripHit(x, y, 2)) return XZ_TOUCH_WEAPON3;
	if (Xziel_IsInside(x, y, xziel_hud_fire_x.value, xziel_hud_fire_y.value, 0.073f * hs * xziel_hud_fire_scale.value)) return XZ_TOUCH_FIRE;
	if (Xziel_IsInside(x, y, xziel_hud_adsfire_x.value, xziel_hud_adsfire_y.value, 0.056f * hs * xziel_hud_adsfire_scale.value)) return XZ_TOUCH_ADSFIRE;
	if (Xziel_IsInside(x, y, xziel_hud_ads_x.value, xziel_hud_ads_y.value, 0.047f * hs * xziel_hud_ads_scale.value)) return XZ_TOUCH_ADS;
	if (Xziel_IsInside(x, y, xziel_hud_reload_x.value, xziel_hud_reload_y.value, 0.044f * hs * xziel_hud_reload_scale.value)) return XZ_TOUCH_RELOAD;
	if (xziel_mobile_use_available && Xziel_IsInside(x, y, xziel_hud_use_x.value, xziel_hud_use_y.value, 0.050f * hs * xziel_hud_use_scale.value)) return XZ_TOUCH_USE;
	if (Xziel_IsInside(x, y, xziel_hud_pause_x.value, xziel_hud_pause_y.value, 0.036f * hs * xziel_hud_pause_scale.value)) return XZ_TOUCH_PAUSE;
	if (Xziel_IsInside(x, y, xziel_hud_grenade_x.value, xziel_hud_grenade_y.value, 0.041f * hs * xziel_hud_grenade_scale.value)) return XZ_TOUCH_GRENADE;
	if (Xziel_IsInside(x, y, xziel_hud_jump_x.value, xziel_hud_jump_y.value, 0.044f * hs * xziel_hud_jump_scale.value)) return XZ_TOUCH_JUMP;
	if ((!xziel_mobile_knife_range_only.value || xziel_mobile_knife_target_near) &&
		Xziel_IsInside(x, y, xziel_hud_knife_x.value, xziel_hud_knife_y.value, 0.044f * hs * xziel_hud_knife_scale.value)) return XZ_TOUCH_KNIFE;
	if (x < 0.45f && y > 0.30f) return XZ_TOUCH_MOVE;
	return XZ_TOUCH_LOOK;
}'''
text = replace_function(text, "static xziel_touch_role_t Xziel_RoleForPoint(float x, float y)", role_func)

editor_role = r'''static xziel_touch_role_t Xziel_HudEditorRole(float x, float y)
{
	float hs = xziel_mobile_hud_scale.value;
	if (Xziel_WeaponStripHit(x, y, 0)) return XZ_TOUCH_WEAPONSTRIP;
	if (Xziel_WeaponStripHit(x, y, 1)) return XZ_TOUCH_WEAPON2;
	if (Xziel_WeaponStripHit(x, y, 2)) return XZ_TOUCH_WEAPON3;
	if (Xziel_IsInside(x, y, xziel_hud_fire_x.value, xziel_hud_fire_y.value, 0.090f * hs * xziel_hud_fire_scale.value)) return XZ_TOUCH_FIRE;
	if (Xziel_IsInside(x, y, xziel_hud_adsfire_x.value, xziel_hud_adsfire_y.value, 0.075f * hs * xziel_hud_adsfire_scale.value)) return XZ_TOUCH_ADSFIRE;
	if (Xziel_IsInside(x, y, xziel_hud_ads_x.value, xziel_hud_ads_y.value, 0.065f * hs * xziel_hud_ads_scale.value)) return XZ_TOUCH_ADS;
	if (Xziel_IsInside(x, y, xziel_hud_reload_x.value, xziel_hud_reload_y.value, 0.060f * hs * xziel_hud_reload_scale.value)) return XZ_TOUCH_RELOAD;
	if (Xziel_IsInside(x, y, xziel_hud_use_x.value, xziel_hud_use_y.value, 0.065f * hs * xziel_hud_use_scale.value)) return XZ_TOUCH_USE;
	if (Xziel_IsInside(x, y, xziel_hud_pause_x.value, xziel_hud_pause_y.value, 0.055f * hs * xziel_hud_pause_scale.value)) return XZ_TOUCH_PAUSE;
	if (Xziel_IsInside(x, y, xziel_hud_grenade_x.value, xziel_hud_grenade_y.value, 0.057f * hs * xziel_hud_grenade_scale.value)) return XZ_TOUCH_GRENADE;
	if (Xziel_IsInside(x, y, xziel_hud_jump_x.value, xziel_hud_jump_y.value, 0.060f * hs * xziel_hud_jump_scale.value)) return XZ_TOUCH_JUMP;
	if (Xziel_IsInside(x, y, xziel_hud_knife_x.value, xziel_hud_knife_y.value, 0.060f * hs * xziel_hud_knife_scale.value)) return XZ_TOUCH_KNIFE;
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
	case XZ_TOUCH_KNIFE: Cvar_SetValue("xziel_hud_knife_x", x); Cvar_SetValue("xziel_hud_knife_y", y); break;
	case XZ_TOUCH_GRENADE: Cvar_SetValue("xziel_hud_grenade_x", x); Cvar_SetValue("xziel_hud_grenade_y", y); break;
	case XZ_TOUCH_PAUSE: Cvar_SetValue("xziel_hud_pause_x", x); Cvar_SetValue("xziel_hud_pause_y", y); break;
	case XZ_TOUCH_WEAPONSTRIP: Cvar_SetValue("xziel_hud_weapon1_x", x); Cvar_SetValue("xziel_hud_weapon1_y", y); break;
	case XZ_TOUCH_WEAPON2: Cvar_SetValue("xziel_hud_weapon2_x", x); Cvar_SetValue("xziel_hud_weapon2_y", y); break;
	case XZ_TOUCH_WEAPON3: Cvar_SetValue("xziel_hud_pistol_x", x); Cvar_SetValue("xziel_hud_pistol_y", y); break;
	default: break;
	}
}'''
text = replace_function(text, "static void Xziel_HudEditorSetPosition(xziel_touch_role_t role, float x, float y)", editor_set)

finger_down = r'''static void Xziel_FingerDown(const SDL_TouchFingerEvent *finger)
{
	xziel_touch_slot_t *slot;
	qboolean menu = (key_dest == key_menu || key_dest == key_menu_pause);

	if (cl.stats[STAT_HEALTH] <= 0 && key_dest == key_game) {
		Xziel_ReleaseAllTouches();
		Menu_ExitMap();
		return;
	}

	if (m_state == m_hudedit && menu) {
		int mx = (int)(finger->x * (float)vid.width);
		int my = (int)(finger->y * (float)vid.height);
		int row;

		/* Editor widgets always win over draggable HUD controls. This fixes
		   Reset Layout / Done being swallowed by the joystick/control hitbox. */
		Menu_MouseMove(mx, my);
		if (Menu_MouseButton(mx, my, true)) {
			xziel_menu_touch_active = true;
			xziel_menu_touch_finger = finger->fingerId;
			xziel_menu_touch_state = m_state;
			return;
		}
		row = Xziel_MenuButtonAtPoint(mx, my);
		if (row >= 0) {
			Xziel_MenuSetCursor(row);
			Menu_ButtonPress();
			xziel_menu_touch_active = false;
			xziel_menu_touch_state = -1;
			return;
		}

		xziel_touch_role_t role = Xziel_HudEditorRole(finger->x, finger->y);
		if (role != XZ_TOUCH_NONE && role != XZ_TOUCH_LOOK) {
			xziel_hud_editor_selected = role;
			slot = Xziel_AllocTouch(finger->fingerId);
			if (slot) {
				slot->editor_drag = true;
				slot->role = role;
				slot->last_x = finger->x;
				slot->last_y = finger->y;
				Xziel_HudEditorSetPosition(role, finger->x, finger->y);
			}
			return;
		}
		return;
	}

	if (menu) {
		xziel_menu_touch_active = true;
		xziel_menu_touch_finger = finger->fingerId;
		xziel_menu_touch_state = m_state;
		Xziel_MenuFinger(finger->x, finger->y, true, false);
		return;
	}

	if (key_dest != key_game)
		return;

	slot = Xziel_AllocTouch(finger->fingerId);
	if (!slot)
		return;

	slot->role = Xziel_RoleForPoint(finger->x, finger->y);
	slot->last_x = finger->x;
	slot->last_y = finger->y;
	if (slot->role == XZ_TOUCH_MOVE) {
		xziel_mobile_move_anchor_x = xziel_hud_joy_x.value;
		xziel_mobile_move_anchor_y = xziel_hud_joy_y.value;
		Xziel_UpdateMove(finger->x, finger->y);
	} else if (slot->role != XZ_TOUCH_LOOK) {
		Xziel_ActionDown(slot->role);
	}
}'''
text = replace_function(text, "static void Xziel_FingerDown(const SDL_TouchFingerEvent *finger)", finger_down)

finger_motion = r'''static void Xziel_FingerMotion(const SDL_TouchFingerEvent *finger)
{
	xziel_touch_slot_t *slot = Xziel_FindTouch(finger->fingerId);
	if (slot && slot->editor_drag) {
		Xziel_HudEditorSetPosition(slot->role, finger->x, finger->y);
		slot->last_x = finger->x;
		slot->last_y = finger->y;
		return;
	}
	if (key_dest == key_menu || key_dest == key_menu_pause) {
		if (xziel_menu_touch_active &&
			xziel_menu_touch_finger == finger->fingerId &&
			xziel_menu_touch_state == m_state)
			Xziel_MenuFinger(finger->x, finger->y, false, true);
		return;
	}
	if (!slot)
		return;
	if (slot->role == XZ_TOUCH_MOVE) {
		Xziel_UpdateMove(finger->x, finger->y);
	} else if (slot->role == XZ_TOUCH_LOOK ||
		slot->role == XZ_TOUCH_FIRE ||
		slot->role == XZ_TOUCH_ADSFIRE ||
		slot->role == XZ_TOUCH_ADS ||
		slot->role == XZ_TOUCH_GRENADE) {
		float look_scale = xziel_mobile_touch_sensitivity.value;
		qboolean firing_touch =
			slot->role == XZ_TOUCH_FIRE ||
			slot->role == XZ_TOUCH_ADSFIRE ||
			slot->role == XZ_TOUCH_GRENADE;

		if (cl.stats[STAT_ZOOM] == 2)
			look_scale *= firing_touch ?
				xziel_mobile_sniper_fire_sensitivity.value :
				xziel_mobile_sniper_sensitivity.value;
		else if (cl.stats[STAT_ZOOM] == 1)
			look_scale *= firing_touch ?
				xziel_mobile_ads_fire_sensitivity.value :
				xziel_mobile_ads_sensitivity.value;
		else if (firing_touch)
			look_scale *= xziel_mobile_fire_sensitivity.value;

		mouse_dx += (int)((finger->x - slot->last_x) * (float)vid.width * look_scale);
		mouse_dy += (int)((finger->y - slot->last_y) * (float)vid.height * look_scale);
	}
	slot->last_x = finger->x;
	slot->last_y = finger->y;
}'''
text = replace_function(text, "static void Xziel_FingerMotion(const SDL_TouchFingerEvent *finger)", finger_motion)

sdl.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# HUD: CC0 icon assets + per-control alpha/scale + independent weapon cards.
# ---------------------------------------------------------------------------
hud = source / "render" / "r_hud.c"
htext = hud.read_text(encoding="utf-8")

hud_anchor = "extern cvar_t xziel_hud_grenade_y;\n"
hud_extern_lines = []
for name in control_defaults:
    hud_extern_lines += [
        f"extern cvar_t xziel_hud_{name}_scale;",
        f"extern cvar_t xziel_hud_{name}_opacity;",
    ]
for name in ("weapon1_x", "weapon1_y", "weapon1_scale", "weapon1_opacity",
             "weapon2_x", "weapon2_y", "weapon2_scale", "weapon2_opacity",
             "pistol_x", "pistol_y", "pistol_scale", "pistol_opacity"):
    hud_extern_lines.append(f"extern cvar_t xziel_hud_{name};")
hud_extern_block = "\n".join(hud_extern_lines) + "\n"
if "extern cvar_t xziel_hud_fire_scale;" not in htext:
    htext = must_replace(htext, hud_anchor, hud_anchor + hud_extern_block, "HUD v0.18 externs")

image_anchor = "static image_t hud_hitmarker;\n"
image_defs = r'''static image_t xziel_icon_fire;
static image_t xziel_icon_ads;
static image_t xziel_icon_reload;
static image_t xziel_icon_use;
static image_t xziel_icon_jump;
static image_t xziel_icon_knife;
static image_t xziel_icon_grenade;
static image_t xziel_icon_pause;
static image_t xziel_icon_sprint;
static image_t xziel_icon_pistol;
static image_t xziel_icon_weapon;
static image_t xziel_icon_threat;
'''
if "xziel_icon_fire" not in htext:
    htext = must_replace(htext, image_anchor, image_anchor + image_defs, "Xziel icon handles")

load_anchor = '    hud_hitmarker = Image_LoadImage("gfx/hud/hit_marker", IMAGE_TGA, 0, true, false);\n'
load_code = r'''    xziel_icon_fire    = Image_LoadImage("gfx/xziel/fire", IMAGE_PNG, 0, true, false);
    xziel_icon_ads     = Image_LoadImage("gfx/xziel/ads", IMAGE_PNG, 0, true, false);
    xziel_icon_reload  = Image_LoadImage("gfx/xziel/reload", IMAGE_PNG, 0, true, false);
    xziel_icon_use     = Image_LoadImage("gfx/xziel/use", IMAGE_PNG, 0, true, false);
    xziel_icon_jump    = Image_LoadImage("gfx/xziel/jump", IMAGE_PNG, 0, true, false);
    xziel_icon_knife   = Image_LoadImage("gfx/xziel/knife", IMAGE_PNG, 0, true, false);
    xziel_icon_grenade = Image_LoadImage("gfx/xziel/grenade", IMAGE_PNG, 0, true, false);
    xziel_icon_pause   = Image_LoadImage("gfx/xziel/pause", IMAGE_PNG, 0, true, false);
    xziel_icon_sprint  = Image_LoadImage("gfx/xziel/sprint", IMAGE_PNG, 0, true, false);
    xziel_icon_pistol  = Image_LoadImage("gfx/xziel/pistol", IMAGE_PNG, 0, true, false);
    xziel_icon_weapon  = Image_LoadImage("gfx/xziel/weapon", IMAGE_PNG, 0, true, false);
    xziel_icon_threat  = Image_LoadImage("gfx/xziel/threat", IMAGE_PNG, 0, true, false);
'''
if 'Image_LoadImage("gfx/xziel/fire"' not in htext:
    htext = must_replace(htext, load_anchor, load_anchor + load_code, "Xziel icon loading")

style_helper = r'''
static void Xziel_ControlStyle(const char *label1, const char *label2, float *scale, float *opacity)
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
	else if (!strcmp(label1, "II")) { *scale = xziel_hud_pause_scale.value; *opacity = xziel_hud_pause_opacity.value; }
	if (*scale < 0.50f) *scale = 0.50f;
	if (*scale > 1.80f) *scale = 1.80f;
	if (*opacity < 0.15f) *opacity = 0.15f;
	if (*opacity > 1.00f) *opacity = 1.00f;
}

static image_t Xziel_ActionIcon(const char *label1, const char *label2)
{
	if (!strcmp(label1, "FIRE")) return xziel_icon_fire;
	if (!strcmp(label1, "ADS")) return xziel_icon_ads;
	if (!strcmp(label1, "RLD")) return xziel_icon_reload;
	if (!strcmp(label1, "USE")) return xziel_icon_use;
	if (!strcmp(label1, "JUMP")) return xziel_icon_jump;
	if (!strcmp(label1, "KNIFE")) return xziel_icon_knife;
	if (!strcmp(label1, "NADE")) return xziel_icon_grenade;
	if (!strcmp(label1, "II")) return xziel_icon_pause;
	return 0;
}
'''
if "static void Xziel_ControlStyle" not in htext:
    idx = htext.find("static qboolean Xziel_DrawActionGlyph")
    if idx < 0:
        raise SystemExit("Could not find action glyph helper")
    htext = htext[:idx] + style_helper + "\n" + htext[idx:]

action_glyph = r'''static qboolean Xziel_DrawActionGlyph(int cx, int cy, int radius,
	const char *label1, const char *label2, qboolean pressed)
{
	float local_scale, local_opacity;
	int size, alpha;
	image_t icon = Xziel_ActionIcon(label1, label2);
	Xziel_ControlStyle(label1, label2, &local_scale, &local_opacity);
	if (!icon) return false;
	size = (int)(radius * 1.15f);
	if (size < 12) size = 12;
	alpha = (int)((pressed ? 255 : 235) * xziel_mobile_hud_opacity.value * local_opacity);
	Draw_ColoredStretchPic(cx - size/2, cy - size/2, icon, size, size, 255,255,255,alpha);
	if (!strcmp(label1, "ADS") && label2 && !strcmp(label2, "FIRE")) {
		int dot = (int)fmaxf(3.0f, 3.0f * vid.scale);
		Draw_FillByColor(cx + size/4, cy + size/5, dot, dot, 255,255,255,alpha);
	}
	return true;
}'''
_action_sig = "static qboolean Xziel_DrawActionGlyph("
_action_pos = htext.rfind(_action_sig)
if _action_pos < 0:
    raise SystemExit("Could not find Xziel_DrawActionGlyph implementation")
htext = htext[:_action_pos] + replace_function(htext[_action_pos:], _action_sig, action_glyph)

touch_button = r'''static void Xziel_DrawTouchButton(float nx, float ny, float radius_h,
	const char *label1, const char *label2, qboolean pressed, qboolean editor)
{
	float local_scale, local_opacity;
	int cx = (int)(nx * vid.width);
	int cy = (int)(ny * vid.height);
	int radius;
	int alpha;
	Xziel_ControlStyle(label1, label2, &local_scale, &local_opacity);
	radius = (int)(radius_h * vid.height * xziel_mobile_hud_scale.value * local_scale);
	if (radius < 10) radius = 10;
	alpha = (int)((pressed ? 98 : 68) * xziel_mobile_hud_opacity.value * local_opacity);
	if (editor) alpha = (int)(110 * xziel_mobile_hud_opacity.value * local_opacity);
	Xziel_DrawDisc(cx, cy, radius, 245,245,245,alpha);
	Xziel_DrawDisc(cx, cy, radius - (int)fmaxf(1.0f, 2.0f*vid.scale), 18,18,18,
		(int)(145 * xziel_mobile_hud_opacity.value * local_opacity));
	if (!Xziel_DrawActionGlyph(cx, cy, radius, label1, label2, pressed)) {
		int tw = getTextWidth((char*)label1, vid.scale);
		Draw_ColoredString(cx - tw/2, cy - (int)(4*vid.scale), (char*)label1,
			255,255,255,(int)(230*local_opacity),vid.scale);
	}
}'''
# Touch renderer is emitted in final scalable/editor-aware form by
# patch_vril_weaponhud.py. Do not re-replace it here.

weapon_glyph = r'''static void Xziel_DrawWeaponGlyph(int cx, int cy, int id, float scale, int alpha)
{
	image_t icon = Xziel_HUDIsPistol(id) ? xziel_icon_pistol : xziel_icon_weapon;
	int size = (int)(30 * scale);
	if (size < 14) size = 14;
	Draw_ColoredStretchPic(cx - size/2, cy - size/2, icon, size, size, 255,255,255,alpha);
}'''
htext = replace_function(htext, "static void Xziel_DrawWeaponGlyph(int cx, int cy, int id, float scale, int alpha)", weapon_glyph)

weapon_card = r'''static void Xziel_DrawWeaponCard(int cx, int cy, int w, int h,
	int weapon, int mag, int reserve, qboolean active, qboolean editor,
	float opacity, const char *slot_name)
{
	int alpha = (int)((active ? 185 : 122) * xziel_mobile_hud_opacity.value * opacity);
	int border = (int)((active ? 255 : 190) * xziel_mobile_hud_opacity.value * opacity);
	int inset = (int)fmaxf(1.0f, 2.0f * vid.scale);
	char ammo[32];
	int tw;
	if (opacity < 0.15f) opacity = 0.15f;
	Draw_FillByColor(cx-w/2, cy-h/2, w, h, active ? 42 : 20, active ? 42 : 20, active ? 42 : 20, alpha);
	Draw_FillByColor(cx-w/2, cy-h/2, w, inset, active ? 245 : 185, active ? 196 : 185, active ? 36 : 185, border);
	if (weapon != 0)
		Xziel_DrawWeaponGlyph(cx, cy - h/10, weapon, h/34.0f,
			(int)(235*xziel_mobile_hud_opacity.value*opacity));
	if (editor && weapon == 0)
		Draw_ColoredString(cx - getTextWidth("EMPTY", vid.scale*0.70f)/2, cy-3*vid.scale,
			"EMPTY", 205,205,205,(int)(200*opacity),vid.scale*0.70f);
	snprintf(ammo, sizeof(ammo), "%d/%d", mag, reserve);
	tw = getTextWidth(ammo, vid.scale*0.65f);
	Draw_ColoredString(cx+w/2-tw-(int)(4*vid.scale), cy+h/2-(int)(9*vid.scale), ammo,
		235,235,235,(int)(230*opacity),vid.scale*0.65f);
	Draw_ColoredString(cx-w/2+(int)(3*vid.scale), cy-h/2+(int)(4*vid.scale),
		(char*)slot_name, 218,218,218,(int)(215*opacity),vid.scale*0.55f);
}'''
htext = replace_function(htext, "static void Xziel_DrawWeaponCard(", weapon_card)

weapon_strip = r'''static void Xziel_DrawWeaponStrip(qboolean editor)
{
	struct carddef { float x,y,s,o; int weapon,mag,reserve; const char *name; qboolean active; } c[3];
	c[0].x=xziel_hud_weapon1_x.value; c[0].y=xziel_hud_weapon1_y.value; c[0].s=xziel_hud_weapon1_scale.value; c[0].o=xziel_hud_weapon1_opacity.value;
	c[0].weapon=cl.stats[STAT_ACTIVEWEAPON]; c[0].mag=cl.stats[STAT_CURRENTMAG]; c[0].reserve=cl.stats[STAT_AMMO]; c[0].name="WEAPON 1"; c[0].active=true;
	c[1].x=xziel_hud_weapon2_x.value; c[1].y=xziel_hud_weapon2_y.value; c[1].s=xziel_hud_weapon2_scale.value; c[1].o=xziel_hud_weapon2_opacity.value;
	c[1].weapon=cl.stats[STAT_XZIEL_W2]; c[1].mag=cl.stats[STAT_XZIEL_W2MAG]; c[1].reserve=cl.stats[STAT_XZIEL_W2RES]; c[1].name="WEAPON 2"; c[1].active=false;
	c[2].x=xziel_hud_pistol_x.value; c[2].y=xziel_hud_pistol_y.value; c[2].s=xziel_hud_pistol_scale.value; c[2].o=xziel_hud_pistol_opacity.value;
	c[2].weapon=cl.stats[STAT_XZIEL_W3]; c[2].mag=cl.stats[STAT_XZIEL_W3MAG]; c[2].reserve=cl.stats[STAT_XZIEL_W3RES]; c[2].name="WEAPON 3"; c[2].active=false;
	for (int i=0;i<3;i++) {
		int w = (int)((i==0 ? 96 : 78) * vid.scale * c[i].s);
		int h = (int)((i==0 ? 54 : 48) * vid.scale * c[i].s);
		if (!editor && c[i].weapon == 0) continue;
		Xziel_DrawWeaponCard((int)(c[i].x*vid.width),(int)(c[i].y*vid.height),
			w,h,c[i].weapon,c[i].mag,c[i].reserve,c[i].active,editor,c[i].o,c[i].name);
	}
}'''
htext = replace_function(htext, "static void Xziel_DrawWeaponStrip(qboolean editor)", weapon_strip)

mobile_hud = htext[htext.find("static void Xziel_MobileHUD_DrawInternal(qboolean editor)"):]
# The v0.18 touch renderer takes the editor flag so selected controls can be
# drawn more clearly. All calls live inside this internal draw function and
# are single-line calls in the current Vril mobile HUD.
_mobile_lines = []
for _line in mobile_hud.splitlines(True):
    if "Xziel_DrawTouchButton(" in _line and _line.rstrip().endswith(");") and ", editor);" not in _line:
        _line = _line.replace(");", ", editor);", 1)
    _mobile_lines.append(_line)
mobile_hud = "".join(_mobile_lines)

# Patch only joystick radius/alpha expressions in the final mobile HUD function.
mobile_hud_new = mobile_hud.replace(
    "radius = (int)(0.095f * vid.height * xziel_mobile_hud_scale.value);",
    "radius = (int)(0.095f * vid.height * xziel_mobile_hud_scale.value * xziel_hud_joy_scale.value);",
    1,
).replace(
    "(int)(70 * xziel_mobile_hud_opacity.value)",
    "(int)(70 * xziel_mobile_hud_opacity.value * xziel_hud_joy_opacity.value)",
    1,
).replace(
    "(int)(95 * xziel_mobile_hud_opacity.value)",
    "(int)(95 * xziel_mobile_hud_opacity.value * xziel_hud_joy_opacity.value)",
    1,
)
htext = htext[:htext.find("static void Xziel_MobileHUD_DrawInternal(qboolean editor)")] + mobile_hud_new
hud.write_text(htext, encoding="utf-8")


# ---------------------------------------------------------------------------
# Custom HUD editor UI: select/drag a control, then scale and opacity just that
# selected object. Weapon cards are independent objects, not a group.
# ---------------------------------------------------------------------------
controls = source / "menu" / "menu_controls.c"
ctext = controls.read_text(encoding="utf-8")

menu_extern_anchor = "extern cvar_t xziel_mobile_hud_opacity;\n"
menu_externs = ["extern int xziel_hud_editor_selected;"]
for name in control_defaults:
    menu_externs += [
        f"extern cvar_t xziel_hud_{name}_scale;",
        f"extern cvar_t xziel_hud_{name}_opacity;",
    ]
for name in ("weapon1_x", "weapon1_y", "weapon1_scale", "weapon1_opacity",
             "weapon2_x", "weapon2_y", "weapon2_scale", "weapon2_opacity",
             "pistol_x", "pistol_y", "pistol_scale", "pistol_opacity"):
    menu_externs.append(f"extern cvar_t xziel_hud_{name};")
for name in ("fire_sensitivity", "ads_fire_sensitivity", "sniper_sensitivity",
             "sniper_fire_sensitivity", "gyro_ads_mult", "gyro_sniper_mult"):
    menu_externs.append(f"extern cvar_t xziel_mobile_{name};")
menu_extern_block = "\n".join(menu_externs) + "\n"
if "extern int xziel_hud_editor_selected;" not in ctext:
    ctext = must_replace(ctext, menu_extern_anchor, menu_extern_anchor + menu_extern_block, "menu v0.18 externs")

reset = r'''static void Menu_HudEdit_Reset(void)
{
	Cvar_SetValue("xziel_hud_joy_x", 0.17f); Cvar_SetValue("xziel_hud_joy_y", 0.74f);
	Cvar_SetValue("xziel_hud_fire_x", 0.885f); Cvar_SetValue("xziel_hud_fire_y", 0.585f);
	Cvar_SetValue("xziel_hud_adsfire_x", 0.795f); Cvar_SetValue("xziel_hud_adsfire_y", 0.435f);
	Cvar_SetValue("xziel_hud_ads_x", 0.695f); Cvar_SetValue("xziel_hud_ads_y", 0.575f);
	Cvar_SetValue("xziel_hud_reload_x", 0.805f); Cvar_SetValue("xziel_hud_reload_y", 0.785f);
	Cvar_SetValue("xziel_hud_use_x", 0.605f); Cvar_SetValue("xziel_hud_use_y", 0.675f);
	Cvar_SetValue("xziel_hud_jump_x", 0.695f); Cvar_SetValue("xziel_hud_jump_y", 0.790f);
	Cvar_SetValue("xziel_hud_knife_x", 0.915f); Cvar_SetValue("xziel_hud_knife_y", 0.800f);
	Cvar_SetValue("xziel_hud_pause_x", 0.965f); Cvar_SetValue("xziel_hud_pause_y", 0.075f);
	Cvar_SetValue("xziel_hud_grenade_x", 0.835f); Cvar_SetValue("xziel_hud_grenade_y", 0.300f);
	Cvar_SetValue("xziel_hud_weapon1_x", 0.430f); Cvar_SetValue("xziel_hud_weapon1_y", 0.885f);
	Cvar_SetValue("xziel_hud_weapon2_x", 0.555f); Cvar_SetValue("xziel_hud_weapon2_y", 0.885f);
	Cvar_SetValue("xziel_hud_pistol_x", 0.670f); Cvar_SetValue("xziel_hud_pistol_y", 0.885f);
	Cvar_SetValue("xziel_hud_weapon1_scale", 1.0f); Cvar_SetValue("xziel_hud_weapon2_scale", 0.95f); Cvar_SetValue("xziel_hud_pistol_scale", 0.92f);
	Cvar_SetValue("xziel_hud_weapon1_opacity", 0.90f); Cvar_SetValue("xziel_hud_weapon2_opacity", 0.82f); Cvar_SetValue("xziel_hud_pistol_opacity", 0.82f);
	Cvar_SetValue("xziel_hud_joy_scale", 1.0f); Cvar_SetValue("xziel_hud_joy_opacity", 0.78f);
	Cvar_SetValue("xziel_hud_fire_scale", 1.0f); Cvar_SetValue("xziel_hud_fire_opacity", 0.82f);
	Cvar_SetValue("xziel_hud_adsfire_scale", 1.0f); Cvar_SetValue("xziel_hud_adsfire_opacity", 0.82f);
	Cvar_SetValue("xziel_hud_ads_scale", 1.0f); Cvar_SetValue("xziel_hud_ads_opacity", 0.82f);
	Cvar_SetValue("xziel_hud_reload_scale", 1.0f); Cvar_SetValue("xziel_hud_reload_opacity", 0.82f);
	Cvar_SetValue("xziel_hud_use_scale", 1.0f); Cvar_SetValue("xziel_hud_use_opacity", 0.82f);
	Cvar_SetValue("xziel_hud_jump_scale", 1.0f); Cvar_SetValue("xziel_hud_jump_opacity", 0.82f);
	Cvar_SetValue("xziel_hud_knife_scale", 1.0f); Cvar_SetValue("xziel_hud_knife_opacity", 0.82f);
	Cvar_SetValue("xziel_hud_pause_scale", 1.0f); Cvar_SetValue("xziel_hud_pause_opacity", 0.82f);
	Cvar_SetValue("xziel_hud_grenade_scale", 1.0f); Cvar_SetValue("xziel_hud_grenade_opacity", 0.82f);
}'''
ctext = replace_function(ctext, "static void Menu_HudEdit_Reset(void)", reset)

draw_editor = r'''void Menu_HudEdit_Draw(void)
{
	const char *name = "FIRE";
	Menu_DrawCustomBackground(true);
	Menu_DrawMapPanel();
	Menu_DrawTitle("CUSTOM HUD", MENU_COLOR_WHITE);
	Draw_ColoredString((int)(vid.width * 0.5f) - getTextWidth("DRAG A CONTROL - THEN ADJUST IT", vid.scale) / 2,
		(int)(28 * vid.scale), "DRAG A CONTROL - THEN ADJUST IT", 255,255,255,230,vid.scale);
	Xziel_MobileHUD_DrawEditor();

	switch (xziel_hud_editor_selected) {
	case 1: name="MOVEMENT"; break;
	case 3: name="FIRE"; break;
	case 4: name="ADS + FIRE"; break;
	case 5: name="ADS"; break;
	case 6: name="RELOAD"; break;
	case 7: name="USE"; break;
	case 8: name="JUMP"; break;
	case 9: name="KNIFE"; break;
	case 11: name="PAUSE"; break;
	case 12: name="GRENADE"; break;
	case 13: name="WEAPON 2"; break;
	case 14: name="WEAPON 3"; break;
	case 15: name="WEAPON 1"; break;
	default: break;
	}
	Draw_ColoredString((int)(10*vid.scale),(int)(42*vid.scale),(char*)name,255,215,45,255,vid.scale);

#define DRAW_STYLE(CVAR_SCALE,CVAR_OPACITY) \
	Menu_DrawButton(1, 0, "SCALE", "Resize selected HUD control.", NULL); \
	Menu_DrawOptionSlider(1, 0, 0.50f, 1.80f, CVAR_SCALE, #CVAR_SCALE, false, true, 0.05f); \
	Menu_DrawButton(2, 1, "OPACITY", "Opacity for selected HUD control.", NULL); \
	Menu_DrawOptionSlider(2, 1, 0.15f, 1.00f, CVAR_OPACITY, #CVAR_OPACITY, false, true, 0.05f)

	switch (xziel_hud_editor_selected) {
	case 1: DRAW_STYLE(xziel_hud_joy_scale, xziel_hud_joy_opacity); break;
	case 3: DRAW_STYLE(xziel_hud_fire_scale, xziel_hud_fire_opacity); break;
	case 4: DRAW_STYLE(xziel_hud_adsfire_scale, xziel_hud_adsfire_opacity); break;
	case 5: DRAW_STYLE(xziel_hud_ads_scale, xziel_hud_ads_opacity); break;
	case 6: DRAW_STYLE(xziel_hud_reload_scale, xziel_hud_reload_opacity); break;
	case 7: DRAW_STYLE(xziel_hud_use_scale, xziel_hud_use_opacity); break;
	case 8: DRAW_STYLE(xziel_hud_jump_scale, xziel_hud_jump_opacity); break;
	case 9: DRAW_STYLE(xziel_hud_knife_scale, xziel_hud_knife_opacity); break;
	case 11: DRAW_STYLE(xziel_hud_pause_scale, xziel_hud_pause_opacity); break;
	case 12: DRAW_STYLE(xziel_hud_grenade_scale, xziel_hud_grenade_opacity); break;
	case 13: DRAW_STYLE(xziel_hud_weapon2_scale, xziel_hud_weapon2_opacity); break;
	case 14: DRAW_STYLE(xziel_hud_pistol_scale, xziel_hud_pistol_opacity); break;
	case 15: DRAW_STYLE(xziel_hud_weapon1_scale, xziel_hud_weapon1_opacity); break;
	default: DRAW_STYLE(xziel_hud_fire_scale, xziel_hud_fire_opacity); break;
	}
#undef DRAW_STYLE

	Menu_DrawButton(-2, 2, "RESET LAYOUT", "Restore default mobile HUD positions and control styles.", Menu_HudEdit_Reset);
	Menu_DrawButton(-1, 3, "DONE", "Save HUD layout and return.", Menu_HudEdit_Done);
}'''
ctext = replace_function(ctext, "void Menu_HudEdit_Draw(void)", draw_editor)

# Replace the final Mobile Aim page with the relevant subset of COD Mobile's
# Camera/Firing sensitivity families. We intentionally do not invent 3x/4x/6x
# scope classes that NZ:P does not have.
mobile_aim = r'''void Menu_MobileAim_Draw(void)
{
	int b=1, i=0;
	Menu_DrawCustomBackground(true);
	Menu_DrawMapPanel();
	Menu_DrawTitle("MOBILE AIM", MENU_COLOR_WHITE);
	Menu_DrawButton(b++, i++, "CAMERA - STANDARD", "Look sensitivity while not aiming.", NULL);
	Menu_DrawOptionSlider(b-1, i-1, 0.25f, 4.0f, xziel_mobile_touch_sensitivity, "xziel_mobile_touch_sensitivity", false, true, 0.05f);
	Menu_DrawButton(b++, i++, "CAMERA - ADS", "Look multiplier while aiming down sights.", NULL);
	Menu_DrawOptionSlider(b-1, i-1, 0.15f, 1.5f, xziel_mobile_ads_sensitivity, "xziel_mobile_ads_sensitivity", false, true, 0.05f);
	Menu_DrawButton(b++, i++, "CAMERA - SNIPER", "Look multiplier for scoped sniper ADS.", NULL);
	Menu_DrawOptionSlider(b-1, i-1, 0.10f, 1.5f, xziel_mobile_sniper_sensitivity, "xziel_mobile_sniper_sensitivity", false, true, 0.05f);
	Menu_DrawButton(b++, i++, "FIRING - STANDARD", "Look multiplier while dragging a fire control.", NULL);
	Menu_DrawOptionSlider(b-1, i-1, 0.25f, 2.0f, xziel_mobile_fire_sensitivity, "xziel_mobile_fire_sensitivity", false, true, 0.05f);
	Menu_DrawButton(b++, i++, "FIRING - ADS", "Look multiplier while firing in ADS.", NULL);
	Menu_DrawOptionSlider(b-1, i-1, 0.15f, 1.5f, xziel_mobile_ads_fire_sensitivity, "xziel_mobile_ads_fire_sensitivity", false, true, 0.05f);
	Menu_DrawButton(b++, i++, "FIRING - SNIPER", "Look multiplier while firing a scoped sniper.", NULL);
	Menu_DrawOptionSlider(b-1, i-1, 0.10f, 1.5f, xziel_mobile_sniper_fire_sensitivity, "xziel_mobile_sniper_fire_sensitivity", false, true, 0.05f);
	Menu_DrawButton(-1, i, "BACK", "Return to Mobile Controls.", Menu_Mobile_Set);
}'''
if "void Menu_MobileAim_Draw(void)" in ctext:
    ctext = replace_function(ctext, "void Menu_MobileAim_Draw(void)", mobile_aim)

controls.write_text(ctext, encoding="utf-8")

print("Xziel v0.18 Vril polish applied.")
