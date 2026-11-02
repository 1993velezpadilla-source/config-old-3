/*
Copyright (C) 1996-1997 Id Software, Inc.
Copyright (C) 2026 NZ:P Team

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.
*/
// input.c -- platform-independent input handling

#include "nzportable_def.h"

extern qboolean croshhairmoving;
extern float crosshair_opacity;
extern cvar_t in_anub_mode;
static in_device_t in_active_device = IN_DEVICE_KEYBOARD_MOUSE;

#ifdef __ANDROID__
cvar_t xziel_mobile_ads_toggle = {"xziel_mobile_ads_toggle", "0", true};
cvar_t xziel_mobile_sprint_threshold = {"xziel_mobile_sprint_threshold", "0.84", true};
cvar_t xziel_mobile_touch_sensitivity = {"xziel_mobile_touch_sensitivity", "1.15", true};
cvar_t xziel_mobile_ads_sensitivity = {"xziel_mobile_ads_sensitivity", "0.62", true};
cvar_t xziel_mobile_joystick_sensitivity = {"xziel_mobile_joystick_sensitivity", "1.00", true};
cvar_t xziel_mobile_ads_move_sensitivity = {"xziel_mobile_ads_move_sensitivity", "0.90", true};
cvar_t xziel_modern_zombies = {"xziel_modern_zombies", "1", true};
cvar_t xziel_mobile_track_fire = {"xziel_mobile_track_fire", "1", true};
cvar_t xziel_mobile_fire_camera_rotation = {"xziel_mobile_fire_camera_rotation", "1", true};
cvar_t xziel_mobile_minimap = {"xziel_mobile_minimap", "1", true};
cvar_t xziel_mobile_minimap_range = {"xziel_mobile_minimap_range", "950", true};
cvar_t xziel_hud_minimap_x = {"xziel_hud_minimap_x", "0.915", true};
cvar_t xziel_hud_minimap_y = {"xziel_hud_minimap_y", "0.155", true};
cvar_t xziel_hud_minimap_scale = {"xziel_hud_minimap_scale", "1.00", true};
cvar_t xziel_hud_minimap_opacity = {"xziel_hud_minimap_opacity", "0.88", true};
cvar_t xziel_mobile_fire_sensitivity = {"xziel_mobile_fire_sensitivity", "1.00", true};
cvar_t xziel_mobile_ads_fire_sensitivity = {"xziel_mobile_ads_fire_sensitivity", "0.62", true};
cvar_t xziel_mobile_sniper_sensitivity = {"xziel_mobile_sniper_sensitivity", "0.42", true};
cvar_t xziel_mobile_sniper_fire_sensitivity = {"xziel_mobile_sniper_fire_sensitivity", "0.42", true};
cvar_t xziel_mobile_gyro_ads_mult = {"xziel_mobile_gyro_ads_mult", "0.65", true};
cvar_t xziel_mobile_gyro_sniper_mult = {"xziel_mobile_gyro_sniper_mult", "0.42", true};
cvar_t xziel_mobile_gyro_boost = {"xziel_mobile_gyro_boost", "5.0", true};
cvar_t xziel_mobile_hud_scale = {"xziel_mobile_hud_scale", "1.0", true};
cvar_t xziel_mobile_hud_opacity = {"xziel_mobile_hud_opacity", "0.72", true};
cvar_t xziel_mobile_unlimited_pistol = {"xziel_mobile_unlimited_pistol", "0", true};
cvar_t xziel_hud_weapons_x = {"xziel_hud_weapons_x", "0.50", true};
cvar_t xziel_hud_weapons_y = {"xziel_hud_weapons_y", "0.885", true};
cvar_t xziel_hud_weapons_scale = {"xziel_hud_weapons_scale", "1.0", true};
cvar_t xziel_mobile_autofire_ms = {"xziel_mobile_autofire_ms", "185", true};
cvar_t xziel_mobile_auto_rebuild = {"xziel_mobile_auto_rebuild", "1", true};
cvar_t xziel_mobile_auto_knife = {"xziel_mobile_auto_knife", "1", true};
cvar_t xziel_mobile_knife_range_only = {"xziel_mobile_knife_range_only", "1", true};
cvar_t xziel_mobile_auto_knife_range = {"xziel_mobile_auto_knife_range", "96", true};
cvar_t xziel_mobile_sprint_zone = {"xziel_mobile_sprint_zone", "1.35", true};
cvar_t xziel_mobile_sniper_adsfire = {"xziel_mobile_sniper_adsfire", "2", true};
cvar_t xziel_mobile_shotgun_adsfire = {"xziel_mobile_shotgun_adsfire", "2", true};
cvar_t xziel_mobile_marksman_adsfire = {"xziel_mobile_marksman_adsfire", "2", true};

#ifdef __ANDROID__
cvar_t xziel_hud_joy_x = {"xziel_hud_joy_x", "0.17", true};
cvar_t xziel_hud_joy_y = {"xziel_hud_joy_y", "0.74", true};
cvar_t xziel_hud_fire_x = {"xziel_hud_fire_x", "0.885", true};
cvar_t xziel_hud_fire_y = {"xziel_hud_fire_y", "0.585", true};
cvar_t xziel_hud_adsfire_x = {"xziel_hud_adsfire_x", "0.795", true};
cvar_t xziel_hud_adsfire_y = {"xziel_hud_adsfire_y", "0.435", true};
cvar_t xziel_hud_ads_x = {"xziel_hud_ads_x", "0.695", true};
cvar_t xziel_hud_ads_y = {"xziel_hud_ads_y", "0.575", true};
cvar_t xziel_hud_reload_x = {"xziel_hud_reload_x", "0.805", true};
cvar_t xziel_hud_reload_y = {"xziel_hud_reload_y", "0.785", true};
cvar_t xziel_hud_use_x = {"xziel_hud_use_x", "0.605", true};
cvar_t xziel_hud_use_y = {"xziel_hud_use_y", "0.675", true};
cvar_t xziel_hud_jump_x = {"xziel_hud_jump_x", "0.695", true};
cvar_t xziel_hud_jump_y = {"xziel_hud_jump_y", "0.790", true};
cvar_t xziel_hud_knife_x = {"xziel_hud_knife_x", "0.915", true};
cvar_t xziel_hud_knife_y = {"xziel_hud_knife_y", "0.800", true};
cvar_t xziel_hud_switch_x = {"xziel_hud_switch_x", "0.905", true};
cvar_t xziel_hud_switch_y = {"xziel_hud_switch_y", "0.300", true};
cvar_t xziel_hud_pause_x = {"xziel_hud_pause_x", "0.965", true};
cvar_t xziel_hud_pause_y = {"xziel_hud_pause_y", "0.075", true};
cvar_t xziel_hud_grenade_x = {"xziel_hud_grenade_x", "0.835", true};
cvar_t xziel_hud_grenade_y = {"xziel_hud_grenade_y", "0.300", true};
cvar_t xziel_hud_joy_scale = {"xziel_hud_joy_scale", "1.00", true};
cvar_t xziel_hud_joy_opacity = {"xziel_hud_joy_opacity", "0.78", true};
cvar_t xziel_hud_fire_scale = {"xziel_hud_fire_scale", "1.00", true};
cvar_t xziel_hud_fire_opacity = {"xziel_hud_fire_opacity", "0.82", true};
cvar_t xziel_hud_adsfire_scale = {"xziel_hud_adsfire_scale", "1.00", true};
cvar_t xziel_hud_adsfire_opacity = {"xziel_hud_adsfire_opacity", "0.82", true};
cvar_t xziel_hud_ads_scale = {"xziel_hud_ads_scale", "1.00", true};
cvar_t xziel_hud_ads_opacity = {"xziel_hud_ads_opacity", "0.82", true};
cvar_t xziel_hud_reload_scale = {"xziel_hud_reload_scale", "1.00", true};
cvar_t xziel_hud_reload_opacity = {"xziel_hud_reload_opacity", "0.82", true};
cvar_t xziel_hud_use_scale = {"xziel_hud_use_scale", "1.00", true};
cvar_t xziel_hud_use_opacity = {"xziel_hud_use_opacity", "0.82", true};
cvar_t xziel_hud_jump_scale = {"xziel_hud_jump_scale", "1.00", true};
cvar_t xziel_hud_jump_opacity = {"xziel_hud_jump_opacity", "0.82", true};
cvar_t xziel_hud_knife_scale = {"xziel_hud_knife_scale", "1.00", true};
cvar_t xziel_hud_knife_opacity = {"xziel_hud_knife_opacity", "0.82", true};
cvar_t xziel_hud_pause_scale = {"xziel_hud_pause_scale", "1.00", true};
cvar_t xziel_hud_pause_opacity = {"xziel_hud_pause_opacity", "0.82", true};
cvar_t xziel_hud_grenade_scale = {"xziel_hud_grenade_scale", "1.00", true};
cvar_t xziel_hud_grenade_opacity = {"xziel_hud_grenade_opacity", "0.82", true};
cvar_t xziel_hud_slide_x = {"xziel_hud_slide_x", "0.745", true};
cvar_t xziel_hud_slide_y = {"xziel_hud_slide_y", "0.825", true};
cvar_t xziel_hud_slide_scale = {"xziel_hud_slide_scale", "1.00", true};
cvar_t xziel_hud_slide_opacity = {"xziel_hud_slide_opacity", "0.82", true};
cvar_t xziel_hud_crouch_x = {"xziel_hud_crouch_x", "0.635", true};
cvar_t xziel_hud_crouch_y = {"xziel_hud_crouch_y", "0.875", true};
cvar_t xziel_hud_prone_x = {"xziel_hud_prone_x", "0.555", true};
cvar_t xziel_hud_prone_y = {"xziel_hud_prone_y", "0.875", true};
cvar_t xziel_hud_weapon1_x = {"xziel_hud_weapon1_x", "0.430", true};
cvar_t xziel_hud_weapon1_y = {"xziel_hud_weapon1_y", "0.885", true};
cvar_t xziel_hud_weapon1_scale = {"xziel_hud_weapon1_scale", "1.00", true};
cvar_t xziel_hud_weapon1_opacity = {"xziel_hud_weapon1_opacity", "0.90", true};
cvar_t xziel_hud_weapon2_x = {"xziel_hud_weapon2_x", "0.555", true};
cvar_t xziel_hud_weapon2_y = {"xziel_hud_weapon2_y", "0.885", true};
cvar_t xziel_hud_weapon2_scale = {"xziel_hud_weapon2_scale", "0.95", true};
cvar_t xziel_hud_weapon2_opacity = {"xziel_hud_weapon2_opacity", "0.82", true};
cvar_t xziel_hud_pistol_x = {"xziel_hud_pistol_x", "0.670", true};
cvar_t xziel_hud_pistol_y = {"xziel_hud_pistol_y", "0.885", true};
cvar_t xziel_hud_pistol_scale = {"xziel_hud_pistol_scale", "0.92", true};
cvar_t xziel_hud_pistol_opacity = {"xziel_hud_pistol_opacity", "0.82", true};
#endif
#endif

#ifdef PLATFORM_SUPPORTS_GYRO
cvar_t in_gyro_mode = {"in_gyro_mode", "0", true};
cvar_t in_gyro_sensitivity_x = {"in_gyro_sensitivity_x", "1.0", true};
cvar_t in_gyro_sensitivity_y = {"in_gyro_sensitivity_y", "1.0", true};
cvar_t in_gyro_zoom_scaling = {"in_gyro_zoom_scaling", "1", true};
#endif
#ifdef PLATFORM_SUPPORTS_RUMBLE
cvar_t in_rumble = {"in_rumble", "1", true};
#endif
#ifdef PLATFORM_SUPPORTS_LIGHTBAR
cvar_t in_lightbar = {"in_lightbar", "1", true};
static double in_lightbar_muzzleflash_time;
static byte in_lightbar_muzzleflash_color[3];
#endif

static float IN_Clamp(float value, float minimum, float maximum)
{
	if (value < minimum)
		return minimum;
	if (value > maximum)
		return maximum;
	return value;
}

void IN_SetActiveDevice(in_device_t device) { in_active_device = device; }
in_device_t IN_GetActiveDevice(void) { return in_active_device; }

qboolean IN_KeyMatchesDevice(int key, in_device_t device)
{
	qboolean gamepad_key =
		(key >= K_BOTTOMFACE && key <= K_RTHUMB) ||
		(key >= K_DPAD_UP && key <= K_DPAD_RIGHT) ||
		(key >= K_JOY1 && key <= K_JOY4);
	return device == IN_DEVICE_GAMEPAD ? gamepad_key : !gamepad_key;
}

qboolean IN_KeyMatchesActiveDevice(int key)
{
	return IN_KeyMatchesDevice(key, in_active_device);
}

void IN_Init(void)
{
#ifdef __ANDROID__
	Cvar_RegisterVariable(&xziel_mobile_ads_toggle);
	Cvar_RegisterVariable(&xziel_mobile_sprint_threshold);
	Cvar_RegisterVariable(&xziel_mobile_touch_sensitivity);
	Cvar_RegisterVariable(&xziel_mobile_ads_sensitivity);
	Cvar_RegisterVariable(&xziel_mobile_joystick_sensitivity);
	Cvar_RegisterVariable(&xziel_mobile_ads_move_sensitivity);
	Cvar_RegisterVariable(&xziel_modern_zombies);
	Cvar_RegisterVariable(&xziel_mobile_track_fire);
	Cvar_RegisterVariable(&xziel_mobile_fire_camera_rotation);
	Cvar_RegisterVariable(&xziel_mobile_minimap);
	Cvar_RegisterVariable(&xziel_mobile_minimap_range);
	Cvar_RegisterVariable(&xziel_hud_minimap_x);
	Cvar_RegisterVariable(&xziel_hud_minimap_y);
	Cvar_RegisterVariable(&xziel_hud_minimap_scale);
	Cvar_RegisterVariable(&xziel_hud_minimap_opacity);
	Cvar_RegisterVariable(&xziel_mobile_fire_sensitivity);
	Cvar_RegisterVariable(&xziel_mobile_ads_fire_sensitivity);
	Cvar_RegisterVariable(&xziel_mobile_sniper_sensitivity);
	Cvar_RegisterVariable(&xziel_mobile_sniper_fire_sensitivity);
	Cvar_RegisterVariable(&xziel_mobile_gyro_ads_mult);
	Cvar_RegisterVariable(&xziel_mobile_gyro_sniper_mult);
	Cvar_RegisterVariable(&xziel_mobile_gyro_boost);
	Cvar_RegisterVariable(&xziel_mobile_hud_scale);
	Cvar_RegisterVariable(&xziel_mobile_hud_opacity);
	Cvar_RegisterVariable(&xziel_mobile_unlimited_pistol);
	Cvar_RegisterVariable(&xziel_hud_weapons_x);
	Cvar_RegisterVariable(&xziel_hud_weapons_y);
	Cvar_RegisterVariable(&xziel_hud_weapons_scale);
	Cvar_RegisterVariable(&xziel_mobile_autofire_ms);
	Cvar_RegisterVariable(&xziel_mobile_auto_rebuild);
	Cvar_RegisterVariable(&xziel_mobile_auto_knife);
	Cvar_RegisterVariable(&xziel_mobile_knife_range_only);
	Cvar_RegisterVariable(&xziel_mobile_auto_knife_range);
	Cvar_RegisterVariable(&xziel_mobile_sprint_zone);
	Cvar_RegisterVariable(&xziel_mobile_sniper_adsfire);
	Cvar_RegisterVariable(&xziel_mobile_shotgun_adsfire);
	Cvar_RegisterVariable(&xziel_mobile_marksman_adsfire);
	Cvar_RegisterVariable(&xziel_hud_joy_x);
	Cvar_RegisterVariable(&xziel_hud_joy_y);
	Cvar_RegisterVariable(&xziel_hud_fire_x);
	Cvar_RegisterVariable(&xziel_hud_fire_y);
	Cvar_RegisterVariable(&xziel_hud_adsfire_x);
	Cvar_RegisterVariable(&xziel_hud_adsfire_y);
	Cvar_RegisterVariable(&xziel_hud_ads_x);
	Cvar_RegisterVariable(&xziel_hud_ads_y);
	Cvar_RegisterVariable(&xziel_hud_reload_x);
	Cvar_RegisterVariable(&xziel_hud_reload_y);
	Cvar_RegisterVariable(&xziel_hud_use_x);
	Cvar_RegisterVariable(&xziel_hud_use_y);
	Cvar_RegisterVariable(&xziel_hud_jump_x);
	Cvar_RegisterVariable(&xziel_hud_jump_y);
	Cvar_RegisterVariable(&xziel_hud_knife_x);
	Cvar_RegisterVariable(&xziel_hud_knife_y);
	Cvar_RegisterVariable(&xziel_hud_switch_x);
	Cvar_RegisterVariable(&xziel_hud_switch_y);
	Cvar_RegisterVariable(&xziel_hud_pause_x);
	Cvar_RegisterVariable(&xziel_hud_pause_y);
	Cvar_RegisterVariable(&xziel_hud_grenade_x);
	Cvar_RegisterVariable(&xziel_hud_grenade_y);
	Cvar_RegisterVariable(&xziel_hud_joy_scale);
	Cvar_RegisterVariable(&xziel_hud_joy_opacity);
	Cvar_RegisterVariable(&xziel_hud_fire_scale);
	Cvar_RegisterVariable(&xziel_hud_fire_opacity);
	Cvar_RegisterVariable(&xziel_hud_adsfire_scale);
	Cvar_RegisterVariable(&xziel_hud_adsfire_opacity);
	Cvar_RegisterVariable(&xziel_hud_ads_scale);
	Cvar_RegisterVariable(&xziel_hud_ads_opacity);
	Cvar_RegisterVariable(&xziel_hud_reload_scale);
	Cvar_RegisterVariable(&xziel_hud_reload_opacity);
	Cvar_RegisterVariable(&xziel_hud_use_scale);
	Cvar_RegisterVariable(&xziel_hud_use_opacity);
	Cvar_RegisterVariable(&xziel_hud_jump_scale);
	Cvar_RegisterVariable(&xziel_hud_jump_opacity);
	Cvar_RegisterVariable(&xziel_hud_knife_scale);
	Cvar_RegisterVariable(&xziel_hud_knife_opacity);
	Cvar_RegisterVariable(&xziel_hud_pause_scale);
	Cvar_RegisterVariable(&xziel_hud_pause_opacity);
	Cvar_RegisterVariable(&xziel_hud_grenade_scale);
	Cvar_RegisterVariable(&xziel_hud_grenade_opacity);
	Cvar_RegisterVariable(&xziel_hud_slide_x);
	Cvar_RegisterVariable(&xziel_hud_slide_y);
	Cvar_RegisterVariable(&xziel_hud_slide_scale);
	Cvar_RegisterVariable(&xziel_hud_slide_opacity);
	Cvar_RegisterVariable(&xziel_hud_crouch_x);
	Cvar_RegisterVariable(&xziel_hud_crouch_y);
	Cvar_RegisterVariable(&xziel_hud_prone_x);
	Cvar_RegisterVariable(&xziel_hud_prone_y);
	Cvar_RegisterVariable(&xziel_hud_weapon1_x);
	Cvar_RegisterVariable(&xziel_hud_weapon1_y);
	Cvar_RegisterVariable(&xziel_hud_weapon1_scale);
	Cvar_RegisterVariable(&xziel_hud_weapon1_opacity);
	Cvar_RegisterVariable(&xziel_hud_weapon2_x);
	Cvar_RegisterVariable(&xziel_hud_weapon2_y);
	Cvar_RegisterVariable(&xziel_hud_weapon2_scale);
	Cvar_RegisterVariable(&xziel_hud_weapon2_opacity);
	Cvar_RegisterVariable(&xziel_hud_pistol_x);
	Cvar_RegisterVariable(&xziel_hud_pistol_y);
	Cvar_RegisterVariable(&xziel_hud_pistol_scale);
	Cvar_RegisterVariable(&xziel_hud_pistol_opacity);
#endif
#ifdef PLATFORM_SUPPORTS_GYRO
	Cvar_RegisterVariable(&in_gyro_mode);
	Cvar_RegisterVariable(&in_gyro_sensitivity_x);
	Cvar_RegisterVariable(&in_gyro_sensitivity_y);
	Cvar_RegisterVariable(&in_gyro_zoom_scaling);
#endif
#ifdef PLATFORM_SUPPORTS_RUMBLE
	Cvar_RegisterVariable(&in_rumble);
#endif
#ifdef PLATFORM_SUPPORTS_LIGHTBAR
	Cvar_RegisterVariable(&in_lightbar);
#endif
	if (IN_PlatformHasGamepad() && !IN_PlatformHasMouse())
		IN_SetActiveDevice(IN_DEVICE_GAMEPAD);
	if (IN_PlatformHasMouse()) IN_SetMouseToRelative(true);
	if (IN_PlatformHasGamepad()) IN_PlatformInit();
}

#ifdef PLATFORM_SUPPORTS_RUMBLE
void IN_StartRumble(int low_frequency, int high_frequency, int duration)
{
	if (!in_rumble.value || duration <= 0)
		return;
	IN_PlatformRumble((unsigned short)IN_Clamp(low_frequency, 0, 65535),
		(unsigned short)IN_Clamp(high_frequency, 0, 65535),
		(unsigned int)duration);
}
#endif

#ifdef PLATFORM_SUPPORTS_LIGHTBAR
void IN_TriggerLightbarMuzzleFlash(int red, int green, int blue)
{
	if (red == 255 && green == 255 && blue == 255) {
		red = 255;
		green = 160;
		blue = 32;
	}
	in_lightbar_muzzleflash_color[0] = (byte)IN_Clamp(red, 0, 255);
	in_lightbar_muzzleflash_color[1] = (byte)IN_Clamp(green, 0, 255);
	in_lightbar_muzzleflash_color[2] = (byte)IN_Clamp(blue, 0, 255);
	in_lightbar_muzzleflash_time = realtime + 0.1;
}

void IN_UpdateLightbar(void)
{
	int red, green, blue;
	int player = cl.viewentity > 0 ? cl.viewentity - 1 : 0;
	float damage_mix = 0.0f;

	if (!in_lightbar.value) {
		IN_PlatformSetLightbar(0, 0, 0);
		return;
	}
	if (realtime < in_lightbar_muzzleflash_time) {
		IN_PlatformSetLightbar(in_lightbar_muzzleflash_color[0],
			in_lightbar_muzzleflash_color[1], in_lightbar_muzzleflash_color[2]);
		return;
	}

	CL_PlayerColor(player, &red, &green, &blue);
	if (cl.stats[STAT_HEALTH] > 0 && cl.stats[STAT_HEALTH] < 100) {
		int pulse_value, pulse_add;
		if (cl.stats[STAT_HEALTH] < 50) {
			pulse_value = abs(((int)(realtime * 100) & 100) - 50);
			pulse_add = 50;
		} else {
			pulse_value = abs(((int)(realtime * 50) & 20) - 10);
			pulse_add = 10;
		}
		damage_mix = (200.0f - ((cl.stats[STAT_HEALTH] + pulse_value)
			/ (100.0f + pulse_add)) * 255.0f) / 255.0f;
		damage_mix = IN_Clamp(damage_mix, 0.0f, 1.0f);
	}
	red = (int)(red + (255 - red) * damage_mix);
	green = (int)(green * (1.0f - damage_mix));
	blue = (int)(blue * (1.0f - damage_mix));
	IN_PlatformSetLightbar((byte)red, (byte)green, (byte)blue);
}
#endif

void IN_Shutdown(void)
{
	if (IN_PlatformHasMouse()) IN_SetMouseToRelative(false);
	if (IN_PlatformHasGamepad()) IN_PlatformShutdown();
}

void IN_Commands(void)
{
	if (IN_PlatformHasGamepad()) IN_PlatformCommands();
#ifdef PLATFORM_SUPPORTS_LIGHTBAR
	IN_UpdateLightbar();
#endif
}

void IN_ClearPendingInput(void)
{
	Key_ClearStates();
	if (IN_PlatformHasMouse()) IN_PlatformClearPendingInput();
}

static float IN_ShapeAxis(float value, float speed, float tolerance, float acceleration)
{
	float magnitude;

	value = IN_Clamp(value, -1.0f, 1.0f);
	magnitude = fabsf(value);
	tolerance = IN_Clamp(tolerance, 0.0f, 0.99f);
	if (magnitude <= tolerance)
		return 0.0f;

	magnitude = (magnitude - tolerance) / (1.0f - tolerance);
	magnitude = powf(magnitude, acceleration) * speed;
	return value < 0.0f ? -magnitude : magnitude;
}

void IN_Move(usercmd_t *cmd)
{
	in_analog_stick_t left, right;
	in_analog_stick_t move_stick, look_stick;
	float speed, look_x, look_y, move_x, move_y;
	float tolerance = in_tolerance.value;
	float acceleration = in_acceleration.value;

	if (key_dest != key_game || cl.paused)
		return;

	left.x = left.y = right.x = right.y = 0.0f;
	if (IN_PlatformHasGamepad()) {
		IN_GetAnalogStick(IN_STICK_LEFT, &left);
		IN_GetAnalogStick(IN_STICK_RIGHT, &right);
		IN_PlatformMove(cmd);
	}
	if (IN_PlatformHasMouse()) IN_PlatformMouseMove(cmd);

#ifdef PLATFORM_SUPPORTS_GYRO
	if ((int)in_gyro_mode.value == 1 || ((int)in_gyro_mode.value == 2 && (cl.stats[STAT_ZOOM] == 1 || cl.stats[STAT_ZOOM] == 2))) {
		float gyro_x, gyro_y;

		if (IN_PlatformGetGyro(&gyro_x, &gyro_y)) {
			const float radians_to_degrees = 57.2957795131f;
			float gyro_scale = 1.0f;

			if (in_gyro_zoom_scaling.value) {
				if (cl.stats[STAT_ZOOM] == 1)
					gyro_scale = 0.5f;
				else if (cl.stats[STAT_ZOOM] == 2)
					gyro_scale = 0.25f;
			}

			V_StopPitchDrift();
#ifdef __ANDROID__
			gyro_scale *= xziel_mobile_gyro_boost.value;
			if (cl.stats[STAT_ZOOM] == 2)
				gyro_scale *= xziel_mobile_gyro_sniper_mult.value;
			else if (cl.stats[STAT_ZOOM] == 1)
				gyro_scale *= xziel_mobile_gyro_ads_mult.value;
#endif
			cl.viewangles[YAW] += gyro_y * radians_to_degrees * in_gyro_sensitivity_x.value * gyro_scale * (float)host_frametime;
			cl.viewangles[PITCH] -= gyro_x * radians_to_degrees * in_gyro_sensitivity_y.value * (m_pitch.value > 0 ? -1.0f : 1.0f) * gyro_scale * (float)host_frametime;
			cl.viewangles[PITCH] = IN_Clamp(cl.viewangles[PITCH], -70.0f, 80.0f);
		}
	}
#endif

#ifdef PLATFORM_HAS_ONE_ANALOG_STICK
	if (in_anub_mode.value) {
		move_stick = left;
		look_stick = right;
	} else {
		move_stick = right;
		look_stick = left;
	}
#else
	move_stick = left;
	look_stick = right;
#endif

	speed = sensitivity.value;
	if (IN_GetActiveDevice() == IN_DEVICE_GAMEPAD && in_aimassist.value &&
		CL_PlayerFacingEnemy() && cl.stats[STAT_CURRENTMAG] > 0)
		speed *= 0.5f;
	if (cl.stats[STAT_ZOOM] == 1)
		speed *= 0.5f;
	else if (cl.stats[STAT_ZOOM] == 2)
		speed *= 0.25f;

	look_x = IN_ShapeAxis(look_stick.x, speed, tolerance, acceleration);
	look_y = IN_ShapeAxis(look_stick.y, speed, tolerance, acceleration);
	V_StopPitchDrift();
	cl.viewangles[YAW] -= 30.0f * look_x * (float)host_frametime;
	cl.viewangles[PITCH] += 30.0f * (m_pitch.value > 0 ? 1.0f : -1.0f)
		* look_y * (float)host_frametime;
	cl.viewangles[PITCH] = IN_Clamp(cl.viewangles[PITCH], -70.0f, 80.0f);

	cl_backspeed = cl_forwardspeed = cl_sidespeed = CL_PlayerMoveSpeed();
	cl_sidespeed *= 0.8f;
	cl_backspeed *= 0.7f;
	move_x = IN_ShapeAxis(move_stick.x, cl_sidespeed, tolerance, acceleration);
	move_y = IN_ShapeAxis(move_stick.y,
		move_stick.y >= 0.0f ? cl_forwardspeed : cl_backspeed,
		tolerance, acceleration);
	if (move_x != 0.0f || move_y != 0.0f) {
		cmd->sidemove = move_x;
		cmd->forwardmove = move_y;
	}

	if (cmd->forwardmove == 0.0f && cmd->sidemove == 0.0f && cl.onground) {
		croshhairmoving = false;
		crosshair_opacity = IN_Clamp(crosshair_opacity + 22.0f, 0.0f, 255.0f);
	} else {
		croshhairmoving = true;
		crosshair_opacity = IN_Clamp(crosshair_opacity - 8.0f, 128.0f, 255.0f);
	}
}
