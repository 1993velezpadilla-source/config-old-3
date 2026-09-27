#!/usr/bin/env python3
"""Add opt-in server-authoritative telemetry for XZIEL emulator agents.

The patch is inert unless the server cvar xziel_bot_telemetry is non-zero.
When enabled, the authoritative SSQC server sends each client a compact JSON
snapshot at 4 Hz using normal Quake console-print messages. That means remote
emulators receive only their own player snapshot, while all tactical world
state is sourced from the server instead of OCR guesses.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_quakec_emulator_bot_telemetry.py <quakec-root>")

root = Path(sys.argv[1])
main = root / "source" / "server" / "main.qc"
if not main.is_file():
    raise SystemExit(f"missing QuakeC server main: {main}")

text = main.read_text(encoding="utf-8")
marker = "void() XzielBot_EmitTelemetry"
if marker in text:
    raise SystemExit("Xziel bot telemetry patch already applied")

anchor = "float zombie_cleaned_w;\nvoid() StartFrame =\n{\n"
if anchor not in text:
    raise SystemExit("could not find StartFrame anchor")

payload = r'''
float xziel_bot_telemetry_next;

string(entity player) XzielBot_WeaponArrayJson =
{
	string out = "[";
	float comma = 0;

	for (float i = 0; i < MAX_PLAYER_WEAPONS; i++) {
		float weapon_id = player.weapons[i].weapon_id;
		if (!weapon_id)
			continue;

		float is_wall = 0;
		float ammo_cost = 0;
		entity wall = find(world, classname, "buy_weapon");
		while (wall != world) {
			if (wall.weapon == weapon_id || EqualNonPapWeapon(weapon_id) == wall.weapon) {
				is_wall = 1;
				ammo_cost = IsPapWeapon(weapon_id) ? wall.pap_cost : wall.cost2;
				break;
			}
			wall = find(wall, classname, "buy_weapon");
		}

		string weapon_name = GetWeaponName(weapon_id, player.weapons[i].weapon_tier);
		out = sprintf(
			"%s%s{\\\"name\\\":\\\"%s\\\",\\\"magazine\\\":%g,\\\"reserve\\\":%g",
			out, comma ? "," : "", weapon_name,
			player.weapons[i].weapon_magazine,
			player.weapons[i].weapon_reserve
		);
		out = sprintf(
			"%s,\\\"wall_weapon\\\":%g,\\\"ammo_cost\\\":%g}",
			out, is_wall, ammo_cost
		);
		comma = 1;
	}
	return strcat(out, "]");
};

string(entity player) XzielBot_ZombiesJson =
{
	string out = "[";
	float comma = 0;
	float emitted = 0;
	entity z = find(world, classname, "ai_zombie");

	while (z != world && emitted < 12) {
		float distance = vlen(z.origin - player.origin);
		if (distance <= 1200 && z.health > 0) {
			out = sprintf(
				"%s%s{\\\"id\\\":%g,\\\"position\\\":[%g,%g,%g]",
				out, comma ? "," : "", emitted + 1,
				z.origin_x, z.origin_y, z.origin_z
			);
			out = sprintf(
				"%s,\\\"health\\\":%g,\\\"targeting_me\\\":%g,\\\"state\\\":\\\"%s\\\"}",
				out, z.health, z.enemy == player, z.aistatus
			);
			comma = 1;
			emitted++;
		}
		z = find(z, classname, "ai_zombie");
	}
	return strcat(out, "]");
};

string(entity player) XzielBot_TeammatesJson =
{
	string out = "[";
	float comma = 0;
	float slot = 1;
	entity teammate = find(world, classname, "player");

	while (teammate != world) {
		if (teammate != player) {
			out = sprintf(
				"%s%s{\\\"slot\\\":%g,\\\"position\\\":[%g,%g,%g]",
				out, comma ? "," : "", slot,
				teammate.origin_x, teammate.origin_y, teammate.origin_z
			);
			out = sprintf(
				"%s,\\\"health\\\":%g,\\\"downed\\\":%g,\\\"bleedout_seconds\\\":%g}",
				out, teammate.health, teammate.downed,
				teammate.downed ? qc_max(teammate.bleedingtime - time, 0) : 999
			);
			comma = 1;
		}
		slot++;
		teammate = find(teammate, classname, "player");
	}
	return strcat(out, "]");
};

string(entity player) XzielBot_InteractablesJson =
{
	string out = "[";
	float comma = 0;
	float id = 1000;
	float emitted = 0;
	entity item;

	item = find(world, classname, "window");
	while (item != world && emitted < 24) {
		if (item.health != -10 && vlen(item.origin - player.origin) <= 1500) {
			out = sprintf(
				"%s%s{\\\"id\\\":%g,\\\"kind\\\":\\\"window\\\",\\\"position\\\":[%g,%g,%g]",
				out, comma ? "," : "", id,
				item.origin_x, item.origin_y, item.origin_z
			);
			out = sprintf(
				"%s,\\\"active\\\":1,\\\"boards\\\":%g,\\\"max_boards\\\":%g,\\\"breached\\\":%g}",
				out, item.health, item.health_delay, item.health <= 0
			);
			comma = 1; id++; emitted++;
		}
		item = find(item, classname, "window");
	}

	item = find(world, classname, "buy_weapon");
	while (item != world && emitted < 24) {
		if (vlen(item.origin - player.origin) <= 1800) {
			out = sprintf(
				"%s%s{\\\"id\\\":%g,\\\"kind\\\":\\\"wall_weapon\\\",\\\"position\\\":[%g,%g,%g]",
				out, comma ? "," : "", id,
				item.origin_x, item.origin_y, item.origin_z
			);
			out = sprintf(
				"%s,\\\"active\\\":1,\\\"cost\\\":%g,\\\"weapon\\\":\\\"%s\\\",\\\"ammo_cost\\\":%g}",
				out, item.cost, GetWeaponName(item.weapon, -1), item.cost2
			);
			comma = 1; id++; emitted++;
		}
		item = find(item, classname, "buy_weapon");
	}

	item = find(world, classname, "mystery");
	while (item != world && emitted < 24) {
		if (vlen(item.origin - player.origin) <= 2200 && item.solid != SOLID_NOT) {
			out = sprintf(
				"%s%s{\\\"id\\\":%g,\\\"kind\\\":\\\"mystery_box\\\",\\\"position\\\":[%g,%g,%g]",
				out, comma ? "," : "", id,
				item.origin_x, item.origin_y, item.origin_z
			);
			out = sprintf("%s,\\\"active\\\":1,\\\"cost\\\":%g}", out, mystery_box_cost);
			comma = 1; id++; emitted++;
		}
		item = find(item, classname, "mystery");
	}

	item = find(world, classname, "door_nzp_cost");
	while (item != world && emitted < 24) {
		if (vlen(item.origin - player.origin) <= 2200) {
			out = sprintf(
				"%s%s{\\\"id\\\":%g,\\\"kind\\\":\\\"door\\\",\\\"position\\\":[%g,%g,%g]",
				out, comma ? "," : "", id,
				item.origin_x, item.origin_y, item.origin_z
			);
			out = sprintf("%s,\\\"active\\\":1,\\\"cost\\\":%g}", out, item.cost);
			comma = 1; id++; emitted++;
		}
		item = find(item, classname, "door_nzp_cost");
	}

	return strcat(out, "]");
};

void() XzielBot_EmitTelemetry =
{
	if (!cvar("xziel_bot_telemetry") || time < xziel_bot_telemetry_next)
		return;

	xziel_bot_telemetry_next = time + 0.25;

	float slot = 1;
	entity player = find(world, classname, "player");
	while (player != world) {
		string phase = Remaining_Zombies <= 0 ? "between" : "active";
		string current_name = player.weapon
			? GetWeaponName(player.weapon, player.weapon_tier)
			: "";

		string payload = sprintf(
			"XzielBotState {\\\"timestamp\\\":%g,\\\"map_id\\\":\\\"%s\\\",\\\"round\\\":%g,\\\"round_phase\\\":\\\"%s\\\"",
			time, mapname, rounds, phase
		);
		payload = sprintf(
			"%s,\\\"player\\\":{\\\"slot\\\":%g,\\\"position\\\":[%g,%g,%g]",
			payload, slot, player.origin_x, player.origin_y, player.origin_z
		);
		payload = sprintf(
			"%s,\\\"yaw\\\":%g,\\\"health\\\":%g,\\\"max_health\\\":%g",
			payload, player.angles_y, player.health, player.max_health
		);
		payload = sprintf(
			"%s,\\\"downed\\\":%g,\\\"points\\\":%g,\\\"current_weapon\\\":\\\"%s\\\"",
			payload, player.downed, player.points, current_name
		);
		payload = sprintf(
			"%s,\\\"weapons\\\":%s},\\\"zombies\\\":%s",
			payload, XzielBot_WeaponArrayJson(player), XzielBot_ZombiesJson(player)
		);
		payload = sprintf(
			"%s,\\\"interactables\\\":%s,\\\"teammates\\\":%s}\\n",
			payload, XzielBot_InteractablesJson(player), XzielBot_TeammatesJson(player)
		);

		// Send only this player's state to its client. The host/server keeps
		// authority over world facts while every emulator can run its own bot.
		sprint(player, PRINT_LOW, payload);

		slot++;
		player = find(player, classname, "player");
	}
};
'''

text = text.replace(anchor, payload + anchor, 1)

hook = "\tGamemode_Frame();\n}"
replacement = "\tGamemode_Frame();\n\tXzielBot_EmitTelemetry();\n}"
if hook not in text:
    raise SystemExit("could not find StartFrame tail")
text = text.replace(hook, replacement, 1)

main.write_text(text, encoding="utf-8")
print("patched XZIEL emulator-bot telemetry")
