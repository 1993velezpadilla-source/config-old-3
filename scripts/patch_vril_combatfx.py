#!/usr/bin/env python3
"""Add Xziel floating damage numbers and off-screen zombie threat indicators."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_vril_combatfx.py <vril-root>")

root = Path(sys.argv[1])
source = root / "source"

# Protocol extension.
protocol = source / "protocol.h"
text = protocol.read_text(encoding="utf-8")
anchor = "#define svc_hudconfig"
if "svc_xzieldamage" not in text:
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit("Could not find svc_hudconfig")
    end = text.find("\n", idx)
    text = text[:end+1] + "#define svc_xzieldamage       59\t// [long] damage [byte] critical\n" + text[end+1:]
protocol.write_text(text, encoding="utf-8")

# Client parser.
clparse = source / "cl_parse.c"
text = clparse.read_text(encoding="utf-8")
if "HUD_XzielDamageNumber" not in text:
    extern_anchor = "extern int current_gamemode;\n"
    if extern_anchor not in text:
        raise SystemExit("Could not find cl_parse extern anchor")
    text = text.replace(
        extern_anchor,
        extern_anchor + "extern void HUD_XzielDamageNumber(int damage, int critical);\n",
        1,
    )

strings_anchor = '\t"svc_hudconfig"\n};'
if '"svc_xzieldamage"' not in text:
    if strings_anchor not in text:
        raise SystemExit("Could not find svc_strings tail")
    text = text.replace(
        strings_anchor,
        '\t"svc_hudconfig",\n\t"svc_xzieldamage"\n};',
        1,
    )

case_anchor = '''\t\tcase svc_hitmark:
\t\t\tHUD_Hitmark(MSG_ReadByte());
\t\t\tbreak;
'''
case_repl = '''\t\tcase svc_hitmark:
\t\t\tHUD_Hitmark(MSG_ReadByte());
\t\t\tbreak;

\t\tcase svc_xzieldamage:
\t\t\tHUD_XzielDamageNumber(MSG_ReadLong(), MSG_ReadByte());
\t\t\tbreak;
'''
if "case svc_xzieldamage:" not in text:
    if case_anchor not in text:
        raise SystemExit("Could not find svc_hitmark parse case")
    text = text.replace(case_anchor, case_repl, 1)
clparse.write_text(text, encoding="utf-8")

# HUD presentation.
hud = source / "render" / "r_hud.c"
text = hud.read_text(encoding="utf-8")

state_anchor = "static int hud_hitmarker_type;\n"
state = r'''
#define XZIEL_DAMAGE_TEXT_MAX 24
typedef struct {
	int damage;
	qboolean critical;
	int lane;
	double start_time;
	qboolean active;
} xziel_damage_text_t;

static xziel_damage_text_t xziel_damage_text[XZIEL_DAMAGE_TEXT_MAX];
static int xziel_damage_text_next;
'''
if "XZIEL_DAMAGE_TEXT_MAX" not in text:
    if state_anchor not in text:
        raise SystemExit("Could not find HUD hitmarker state anchor")
    text = text.replace(state_anchor, state_anchor + state, 1)

helpers_anchor = "static int\nHUD_UltrawideOffset(void)"
combat_code = r'''
void HUD_XzielDamageNumber(int damage, int critical)
{
	xziel_damage_text_t *entry;
	if (damage <= 0)
		return;
	entry = &xziel_damage_text[xziel_damage_text_next];
	entry->damage = damage;
	entry->critical = critical ? true : false;
	entry->lane = xziel_damage_text_next % 7;
	entry->start_time = Sys_FloatTime();
	entry->active = true;
	xziel_damage_text_next = (xziel_damage_text_next + 1) % XZIEL_DAMAGE_TEXT_MAX;
}

static void Xziel_DrawDamageNumbers(void)
{
	static const int lane_x[7] = {-28, -16, -7, 0, 9, 18, 30};
	double now = Sys_FloatTime();
	int i;

	for (i = 0; i < XZIEL_DAMAGE_TEXT_MAX; ++i) {
		xziel_damage_text_t *entry = &xziel_damage_text[i];
		float elapsed, t, alpha, scale;
		int x, y, r, g, b;
		char value[24];

		if (!entry->active)
			continue;
		elapsed = (float)(now - entry->start_time);
		if (elapsed >= 0.62f) {
			entry->active = false;
			continue;
		}

		t = elapsed / 0.62f;
		alpha = elapsed < 0.34f ? 1.0f :
			1.0f - ((elapsed - 0.34f) / 0.28f);
		if (alpha < 0) alpha = 0;

		/* COD Mobile-like cascade: fresh hits appear close to the reticle,
		   separate into narrow lanes, rise, and fade. */
		x = vid.width / 2 + (int)(lane_x[entry->lane] * vid.scale);
		y = (int)(vid.height * 0.455f) -
			(int)((8.0f + 25.0f * t) * vid.scale);
		scale = vid.scale * (entry->critical ? 1.22f : 1.08f);

		snprintf(value, sizeof(value), "%d", entry->damage);
		x -= getTextWidth(value, scale) / 2;

		if (entry->critical) {
			r = 255; g = 215; b = 38;
		} else {
			r = 245; g = 245; b = 245;
		}

		/* Thin dark shadow keeps numbers legible over bright maps. */
		Draw_ColoredString(x + (int)vid.scale, y + (int)vid.scale,
			value, 8, 8, 8, (int)(170 * alpha), scale);
		Draw_ColoredString(x, y, value, r, g, b, (int)(255 * alpha), scale);
	}
}

static qboolean Xziel_IsZombieThreatEntity(entity_t *ent)
{
	const char *name;
	if (!ent || !ent->model)
		return false;
	name = ent->model->name;
	if (!name || !name[0])
		return false;

	/* Body models only; avoid head/arm limb entities generating duplicates. */
	if (!strncmp(name, "models/ai/zb", 12))
		return true;
	if (!strcmp(name, "models/ai/dog.mdl"))
		return true;
	return false;
}

static float Xziel_AngleDelta(float a)
{
	while (a > 180.0f) a -= 360.0f;
	while (a < -180.0f) a += 360.0f;
	return a;
}

static void Xziel_DrawThreatIndicators(void)
{
	float best_dist[3] = {999999.0f, 999999.0f, 999999.0f};
	float best_angle[3] = {0, 0, 0};
	int i, slot;

	if (cl.viewentity <= 0 || cl.viewentity >= cl.num_entities)
		return;

	for (i = 1; i < cl.num_entities; ++i) {
		entity_t *ent;
		float dx, dy, dz, dist, world_yaw, delta;
		if (i == cl.viewentity)
			continue;
		ent = &cl_entities[i];
		if (!Xziel_IsZombieThreatEntity(ent))
			continue;

		dx = ent->origin[0] - cl_entities[cl.viewentity].origin[0];
		dy = ent->origin[1] - cl_entities[cl.viewentity].origin[1];
		dz = ent->origin[2] - cl_entities[cl.viewentity].origin[2];
		dist = sqrtf(dx*dx + dy*dy + dz*dz);
		if (dist < 40.0f || dist > 850.0f)
			continue;

		world_yaw = atan2f(dy, dx) * 57.295779513f;
		delta = Xziel_AngleDelta(world_yaw - cl.viewangles[YAW]);

		/* The normal field of view already communicates frontal threats.
		   Only indicate zombies substantially outside it / behind the player. */
		if (fabsf(delta) < 55.0f)
			continue;

		for (slot = 0; slot < 3; ++slot) {
			if (dist < best_dist[slot]) {
				int move;
				for (move = 2; move > slot; --move) {
					best_dist[move] = best_dist[move-1];
					best_angle[move] = best_angle[move-1];
				}
				best_dist[slot] = dist;
				best_angle[slot] = delta;
				break;
			}
		}
	}

	for (slot = 0; slot < 3; ++slot) {
		int size, x, y, alpha;
		float proximity;
		if (best_dist[slot] >= 999998.0f)
			continue;

		proximity = 1.0f - (best_dist[slot] / 850.0f);
		if (proximity < 0.15f) proximity = 0.15f;
		if (proximity > 1.0f) proximity = 1.0f;

		size = (int)((15.0f + 8.0f * proximity) * vid.scale);
		alpha = (int)(115 + 120 * proximity);

		/* Behind-left / behind-right edge indicators, slightly staggered
		   vertically when several threats are present. */
		x = best_angle[slot] < 0 ?
			(int)(30 * vid.scale) :
			vid.width - (int)(30 * vid.scale) - size;
		y = (int)(vid.height * 0.47f) + slot * (int)(24 * vid.scale);

		Draw_ColoredStretchPic(x, y, xziel_icon_threat,
			size, size, 255,255,255,alpha);
	}
}

'''
if "HUD_XzielDamageNumber" not in text:
    idx = text.find(helpers_anchor)
    if idx < 0:
        raise SystemExit("Could not find HUD helper insertion point")
    text = text[:idx] + combat_code + "\n" + text[idx:]

reset_anchor = "    hud_hitmarker_type        = HITMARK_NORMAL;\n"
reset_repl = reset_anchor + "    memset(xziel_damage_text, 0, sizeof(xziel_damage_text));\n    xziel_damage_text_next = 0;\n"
if "memset(xziel_damage_text" not in text:
    if reset_anchor not in text:
        raise SystemExit("Could not find HUD_NewMap hitmarker reset")
    text = text.replace(reset_anchor, reset_repl, 1)

draw_anchor = "    HUD_DrawHitmark();\n"
draw_repl = "    HUD_DrawHitmark();\n    Xziel_DrawDamageNumbers();\n    Xziel_DrawThreatIndicators();\n"
if "Xziel_DrawDamageNumbers();" not in text:
    if draw_anchor not in text:
        raise SystemExit("Could not find HUD hitmarker draw call")
    text = text.replace(draw_anchor, draw_repl, 1)

hud.write_text(text, encoding="utf-8")

print("Patched Vril Xziel combat feedback.")
