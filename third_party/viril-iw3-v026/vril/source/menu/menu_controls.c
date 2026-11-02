/*
Copyright (C) 2025-2026 NZ:P Team

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  

See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
*/
#include "../nzportable_def.h"
#include "menu_defs.h"

//=============================================================================
/* CONTROLS MENU */

char			*aimassist_string;
char			*invert_string;
char 			*anub_string;

cvar_t			global_sensitivity;

extern cvar_t 	in_aimassist;
extern cvar_t	sensitivity;
extern cvar_t	in_acceleration;
extern cvar_t	in_tolerance;
extern cvar_t	in_anub_mode;
extern cvar_t	m_pitch;
#ifdef PLATFORM_USES_GENERIC_GLYPHS
extern cvar_t    cl_controllerglyphs;
static char     *controller_glyphs_string;
#endif
#ifdef PLATFORM_SUPPORTS_GYRO
extern cvar_t in_gyro_mode;
extern cvar_t in_gyro_sensitivity_x;
extern cvar_t in_gyro_sensitivity_y;
extern cvar_t in_gyro_zoom_scaling;
static char *gyro_mode_string;
static char *gyro_zoom_scaling_string;
#endif
#ifdef PLATFORM_SUPPORTS_RUMBLE
extern cvar_t in_rumble;
static char *rumble_string;
#endif

/*
===============
Menu_Controls_Set
===============
*/
void Menu_Controls_Set (void)
{
	Menu_ResetMenuButtons();

    m_previous_state = m_configuration;
	m_state = m_controls;
}

void Menu_Controls_SetStrings (void)
{
	global_sensitivity = sensitivity;

	if((int)in_aimassist.value == 1) {
		aimassist_string = "ENABLED";
	} else {
		aimassist_string = "DISABLED";
	}

	if((int)m_pitch.value > 0) {
		invert_string = "ENABLED";
	} else {
		invert_string = "DISABLED";
	}

#ifdef PLATFORM_HAS_ONE_ANALOG_STICK
	if((int)in_anub_mode.value == 1) {
		anub_string = "MOVE";
	} else {
		anub_string = "LOOK";
	}
#endif

#ifdef PLATFORM_SUPPORTS_GYRO
	switch ((int)in_gyro_mode.value) {
		case 1: gyro_mode_string = "ENABLED"; break;
		case 2: gyro_mode_string = "ADS ONLY"; break;
	default: gyro_mode_string = "DISABLED"; break;
	}
	gyro_zoom_scaling_string = in_gyro_zoom_scaling.value ? "ENABLED" : "DISABLED";
#endif
#ifdef PLATFORM_SUPPORTS_RUMBLE
	rumble_string = in_rumble.value ? "ENABLED" : "DISABLED";
#endif
}

#ifdef PLATFORM_SUPPORTS_GYRO
static void Menu_Controls_ApplyGyroMode(void)
{
	int mode = (int)in_gyro_mode.value + 1;
	Cvar_SetValue("in_gyro_mode", mode > 2 ? 0 : mode);
}

static void Menu_Controls_ApplyGyroZoomScaling(void)
{
	Cvar_SetValue("in_gyro_zoom_scaling", in_gyro_zoom_scaling.value ? 0 : 1);
}

void Menu_Gyro_Set(void)
{
	Menu_ResetMenuButtons();
	m_previous_state = m_controls;
	m_state = m_gyro;
}
#endif

#ifdef PLATFORM_SUPPORTS_RUMBLE
static void Menu_Controls_ApplyRumble(void)
{
	Cvar_SetValue("in_rumble", in_rumble.value ? 0 : 1);
}
#endif

void Menu_Controls_ApplyAimAssist (void)
{
    float current_aimassist = in_aimassist.value;

    current_aimassist += 1;
    if (current_aimassist > 1) {
        current_aimassist = 0;
    }

    Cvar_SetValue ("in_aimassist", current_aimassist);
}

void Menu_Controls_ApplyLookInversion (void)
{
    float current_lookinversion = m_pitch.value;

    current_lookinversion += 1;
    if (current_lookinversion > 1) {
        current_lookinversion = 0;
    }

    Cvar_SetValue ("m_pitch", current_lookinversion);
}

void Menu_Controls_ApplyAnubMode (void)
{
#ifdef PLATFORM_HAS_ONE_ANALOG_STICK
	float current_anubmode = in_anub_mode.value;

    current_anubmode += 1;
    if (current_anubmode > 1) {
        current_anubmode = 0;
    }

    Cvar_SetValue ("in_anub_mode", current_anubmode);
#endif
}

void Menu_Controls_ApplySettings (void)
{
    // no op
    Menu_SetSound(MENU_SND_ENTER);
}

#ifdef PLATFORM_USES_GENERIC_GLYPHS
static void Menu_Controls_ApplyControllerGlyphs(void)
{
	const char *next = "xbox";
	if (!strcmp(cl_controllerglyphs.string, "xbox")) next = "sony";
	else if (!strcmp(cl_controllerglyphs.string, "sony")) next = "nintendo";
	else if (!strcmp(cl_controllerglyphs.string, "nintendo")) next = "generic";
	Cvar_Set("cl_controllerglyphs", (char *)next);
}

static void Menu_Controls_SetControllerGlyphString(void)
{
	if (!strcmp(cl_controllerglyphs.string, "xbox")) controller_glyphs_string = "MICROSOFT";
	else if (!strcmp(cl_controllerglyphs.string, "sony")) controller_glyphs_string = "SONY";
	else if (!strcmp(cl_controllerglyphs.string, "nintendo")) controller_glyphs_string = "NINTENDO";
	else if (!strcmp(cl_controllerglyphs.string, "generic")) controller_glyphs_string = "GENERIC";
	else controller_glyphs_string = cl_controllerglyphs.string;
}
#endif

/*
===============
Menu_Controls_Draw
===============
*/
void Menu_Controls_Draw (void)
{
	int controls_index = 0;
	int controls_buttons = 1;

	// Background
	Menu_DrawCustomBackground (true);

	// Header
	Menu_DrawTitle ("CONTROL OPTIONS", MENU_COLOR_WHITE);

	Menu_Controls_SetStrings();

	// Map panel makes the background darker
    Menu_DrawMapPanel();

	// Aim Assist
	Menu_DrawButton (controls_buttons++, controls_index++, "AIM ASSIST", "Toggle Assisted-Aim to Improve Targetting.", Menu_Controls_ApplyAimAssist);
	Menu_DrawOptionButton (controls_buttons-1, aimassist_string);

	// Look Sensitivity
	Menu_DrawButton (controls_buttons++, controls_index++, "LOOK SENSITIVITY", "Alter look Sensitivity.", NULL);
	Menu_DrawOptionSlider (controls_buttons-1, controls_index-1, 0, 10, global_sensitivity, "sensitivity", false, true, 1);

	// Look Acceleration
	Menu_DrawButton (controls_buttons++, controls_index++, "LOOK ACCELERATION", "Alter look Acceleration.", NULL);
	Menu_DrawOptionSlider (controls_buttons-1, controls_index-1, 0, 1, in_acceleration, "acceleration", false, true, 0.1f);

	// Look Inversion
	Menu_DrawButton (controls_buttons++, controls_index++, "INVERT LOOK", "Invert Y-Axis Camera Input.", Menu_Controls_ApplyLookInversion);
	Menu_DrawOptionButton (controls_buttons-1, invert_string);

#ifdef PLATFORM_USES_GENERIC_GLYPHS
	Menu_Controls_SetControllerGlyphString();
	Menu_DrawButton(controls_buttons++, controls_index++, "CONTROLLER GLYPHS", "Change the controller glyph tilemap.", Menu_Controls_ApplyControllerGlyphs);
	Menu_DrawOptionButton(controls_buttons-1, controller_glyphs_string);
	Menu_DrawControllerGlyphPreview(controls_buttons-1);
#endif

#ifdef PLATFORM_HAS_ONE_ANALOG_STICK
	// Anub tolerance
	Menu_DrawButton (controls_buttons++, controls_index++, "A-NUB TOLERANCE", "Change A-Nub Tolerance.", NULL);
	Menu_DrawOptionSlider (controls_buttons-1, controls_index-1, 0, 1, in_tolerance, "tolerance", false, true, 0.25f);

	// Anub-mode (look/move)
	Menu_DrawButton (controls_buttons++, controls_index++, "A-NUB MODE", "Toggle between Look and Move A-Nub Options.", Menu_Controls_ApplyAnubMode);
	Menu_DrawOptionButton (controls_buttons-1, anub_string);
#endif

#ifdef PLATFORM_SUPPORTS_RUMBLE
	Menu_DrawButton(controls_buttons++, controls_index++, "RUMBLE", "Enable Game Pad Vibration.", Menu_Controls_ApplyRumble);
	Menu_DrawOptionButton(controls_buttons-1, rumble_string);
#endif

#ifdef PLATFORM_SUPPORTS_GYRO
	Menu_DrawButton(controls_buttons++, controls_index++, "GYROSCOPE", "Configure Gyroscope.", Menu_Gyro_Set);
#endif

	// Bindings
	Menu_DrawButton (controls_buttons++, controls_index++, "BINDINGS", "Change Input Bindings.", Menu_Bindings_Set);

	Menu_DrawDivider(-2.5);
	Menu_DrawButton(-2, controls_index++, "APPLY", "Save & Apply Settings.", Menu_Controls_ApplySettings);
	Menu_DrawButton (-1, controls_index, "BACK", "Return to Main Menu.", Menu_Configuration_Set);
}

#ifdef PLATFORM_SUPPORTS_GYRO
void Menu_Gyro_Draw(void)
{
	int gyro_index = 0;
	int gyro_buttons = 1;

	Menu_DrawCustomBackground(true);
	Menu_DrawTitle("GYRO-AIM OPTIONS", MENU_COLOR_WHITE);
	Menu_DrawMapPanel();
	Menu_Controls_SetStrings();

	Menu_DrawButton(gyro_buttons++, gyro_index++, "MODE", "Toggle Gyroscope behavior.", Menu_Controls_ApplyGyroMode);
	Menu_DrawOptionButton(gyro_buttons-1, gyro_mode_string);

	Menu_DrawButton(gyro_buttons++, gyro_index++, "X-AXIS SENSITIVITY", "Adjust horizontal Gyroscope sensitivity.", NULL);
	Menu_DrawOptionSlider(gyro_buttons-1, gyro_index-1, 0.5f, 15.0f, in_gyro_sensitivity_x, "in_gyro_sensitivity_x", false, true, 0.25f);

	Menu_DrawButton(gyro_buttons++, gyro_index++, "Y-AXIS SENSITIVITY", "Adjust vertical Gyroscope sensitivity.", NULL);
	Menu_DrawOptionSlider(gyro_buttons-1, gyro_index-1, 0.5f, 15.0f, in_gyro_sensitivity_y, "in_gyro_sensitivity_y", false, true, 0.25f);

	Menu_DrawButton(gyro_buttons++, gyro_index++, "GYRO ADS SLOWDOWN", "Reduce gyro sensitivity while aiming down sights.", Menu_Controls_ApplyGyroZoomScaling);
	Menu_DrawOptionButton(gyro_buttons-1, gyro_zoom_scaling_string);

	Menu_DrawButton(-1, gyro_index, "BACK", "Return to Control Options.", Menu_Controls_Set);
}
#endif


#ifdef __ANDROID__
extern cvar_t xziel_mobile_ads_toggle;
extern cvar_t xziel_mobile_sprint_threshold;
extern cvar_t xziel_mobile_touch_sensitivity;
extern cvar_t xziel_mobile_ads_sensitivity;
extern cvar_t xziel_mobile_ads_toggle;
extern cvar_t xziel_mobile_joystick_sensitivity;
extern cvar_t xziel_mobile_ads_move_sensitivity;
extern cvar_t xziel_modern_zombies;
extern cvar_t xziel_mobile_track_fire;
extern cvar_t xziel_mobile_fire_camera_rotation;
extern cvar_t xziel_mobile_minimap;
extern cvar_t xziel_mobile_minimap_range;
extern cvar_t xziel_hud_minimap_x;
extern cvar_t xziel_hud_minimap_y;
extern cvar_t xziel_hud_minimap_scale;
extern cvar_t xziel_hud_minimap_opacity;
extern cvar_t xziel_hud_slide_scale;
extern cvar_t xziel_hud_slide_opacity;
extern cvar_t xziel_mobile_gyro_boost;
extern cvar_t xziel_mobile_hud_scale;
extern cvar_t xziel_mobile_hud_opacity;
extern int xziel_hud_editor_selected;
extern cvar_t xziel_hud_joy_scale;
extern cvar_t xziel_hud_joy_opacity;
extern cvar_t xziel_hud_fire_scale;
extern cvar_t xziel_hud_fire_opacity;
extern cvar_t xziel_hud_adsfire_scale;
extern cvar_t xziel_hud_adsfire_opacity;
extern cvar_t xziel_hud_ads_scale;
extern cvar_t xziel_hud_ads_opacity;
extern cvar_t xziel_hud_reload_scale;
extern cvar_t xziel_hud_reload_opacity;
extern cvar_t xziel_hud_use_scale;
extern cvar_t xziel_hud_use_opacity;
extern cvar_t xziel_hud_jump_scale;
extern cvar_t xziel_hud_jump_opacity;
extern cvar_t xziel_hud_knife_scale;
extern cvar_t xziel_hud_knife_opacity;
extern cvar_t xziel_hud_pause_scale;
extern cvar_t xziel_hud_pause_opacity;
extern cvar_t xziel_hud_grenade_scale;
extern cvar_t xziel_hud_grenade_opacity;
extern cvar_t xziel_hud_weapon1_x;
extern cvar_t xziel_hud_weapon1_y;
extern cvar_t xziel_hud_weapon1_scale;
extern cvar_t xziel_hud_weapon1_opacity;
extern cvar_t xziel_hud_weapon2_x;
extern cvar_t xziel_hud_weapon2_y;
extern cvar_t xziel_hud_weapon2_scale;
extern cvar_t xziel_hud_weapon2_opacity;
extern cvar_t xziel_hud_pistol_x;
extern cvar_t xziel_hud_pistol_y;
extern cvar_t xziel_hud_pistol_scale;
extern cvar_t xziel_hud_pistol_opacity;
extern cvar_t xziel_mobile_fire_sensitivity;
extern cvar_t xziel_mobile_ads_fire_sensitivity;
extern cvar_t xziel_mobile_sniper_sensitivity;
extern cvar_t xziel_mobile_sniper_fire_sensitivity;
extern cvar_t xziel_mobile_gyro_ads_mult;
extern cvar_t xziel_mobile_gyro_sniper_mult;
extern cvar_t xziel_mobile_autofire_ms;
extern cvar_t xziel_mobile_sniper_adsfire;
extern cvar_t xziel_mobile_shotgun_adsfire;
extern cvar_t xziel_mobile_marksman_adsfire;
extern cvar_t xziel_mobile_auto_rebuild;
extern cvar_t xziel_mobile_auto_knife;
extern cvar_t xziel_mobile_knife_range_only;
extern cvar_t xziel_mobile_auto_knife_range;
extern cvar_t xziel_mobile_sprint_zone;
extern cvar_t xziel_mobile_unlimited_pistol;
extern cvar_t xziel_hud_weapons_x;
extern cvar_t xziel_hud_weapons_y;
extern cvar_t xziel_hud_weapons_scale;

static char *xziel_ads_mode_string;
static char *xziel_sniper_fire_string;
static char *xziel_shotgun_fire_string;
static char *xziel_marksman_fire_string;


static const char *Menu_MobileAdsFireModeString(cvar_t *value)
{
	int mode = (int)value->value;
	if (mode == 0) return "PRESS TO FIRE";
	if (mode == 1) return "RELEASE TO FIRE";
	return "AUTO BY WEAPON";
}

static void Menu_MobileCycleSniperFire(void)
{
	Cvar_SetValue("xziel_mobile_sniper_adsfire",
		((int)xziel_mobile_sniper_adsfire.value + 1) % 3);
}

static void Menu_MobileCycleShotgunFire(void)
{
	Cvar_SetValue("xziel_mobile_shotgun_adsfire",
		((int)xziel_mobile_shotgun_adsfire.value + 1) % 3);
}

static void Menu_MobileCycleMarksmanFire(void)
{
	Cvar_SetValue("xziel_mobile_marksman_adsfire",
		((int)xziel_mobile_marksman_adsfire.value + 1) % 3);
}

static void Menu_Mobile_ToggleADS(void)
{
	Cvar_SetValue("xziel_mobile_ads_toggle",
		xziel_mobile_ads_toggle.value >= 0.5f ? 0.0f : 1.0f);
}

void Menu_Mobile_Set(void)
{
	Menu_ResetMenuButtons();
	m_previous_state = m_configuration;
	m_state = m_mobile;
}

void Menu_Mobile_Draw(void)
{
	Menu_DrawCustomBackground(true);
	Menu_DrawTitle("MOBILE SETTINGS", MENU_COLOR_WHITE);
	Menu_DrawMapPanel();

	Menu_DrawButton(1, 0, "AIM & TOUCH", "ADS behavior and touch camera sensitivity.", Menu_MobileAim_Set);
	Menu_DrawButton(2, 1, "GYROSCOPE", "Phone gyroscope mode and sensitivity.", Menu_MobileGyro_Set);
	Menu_DrawButton(3, 2, "HUD & LAYOUT", "HUD size, opacity and custom control placement.", Menu_MobileHud_Set);
	Menu_DrawButton(4, 3, "GAMEPLAY & INTERACTIONS", "Auto sprint and contextual mobile interactions.", Menu_MobileGameplay_Set);

	Menu_DrawButton(-1, 4, "BACK", "Return to Configuration.", Menu_Configuration_Set);
}
#endif


#ifdef __ANDROID__
void Xziel_MobileHUD_DrawEditor(void);
extern void Host_WriteConfiguration(void);

static void Menu_HudEdit_Reset(void)
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
	Cvar_SetValue("xziel_hud_slide_x", 0.745f); Cvar_SetValue("xziel_hud_slide_y", 0.825f);
	Cvar_SetValue("xziel_hud_slide_scale", 1.0f); Cvar_SetValue("xziel_hud_slide_opacity", 0.82f);
	Cvar_SetValue("xziel_hud_minimap_x", 0.915f); Cvar_SetValue("xziel_hud_minimap_y", 0.155f);
	Cvar_SetValue("xziel_hud_minimap_scale", 1.0f); Cvar_SetValue("xziel_hud_minimap_opacity", 0.88f);
}

static void Menu_HudEdit_Done(void)
{
	Host_WriteConfiguration();
	Menu_Mobile_Set();
}

void Menu_HudEdit_Set(void)
{
	Menu_ResetMenuButtons();
	m_previous_state = m_mobile;
	m_state = m_hudedit;
}

void Menu_HudEdit_Draw(void)
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
	case 14: name=xziel_mobile_unlimited_pistol.value >= 0.5f ? "PISTOL SLOT" : "WEAPON 3"; break;
	case 15: name="WEAPON 1"; break;
	case 16: name="CROUCH / SLIDE"; break;
	case 17: name="MINIMAP"; break;
	default: break;
	}
	Draw_ColoredString((int)(10*vid.scale),(int)(42*vid.scale),(char*)name,255,215,45,255,vid.scale);

#define DRAW_STYLE(CVAR_SCALE,CVAR_OPACITY) \
	Menu_DrawButton(1, 0, "SCALE", "Resize selected HUD control.", NULL); \
	Menu_DrawOptionSlider(1, 0, 0.20f, 4.00f, CVAR_SCALE, #CVAR_SCALE, false, true, 0.05f); \
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
	case 16: DRAW_STYLE(xziel_hud_slide_scale, xziel_hud_slide_opacity); break;
	case 17: DRAW_STYLE(xziel_hud_minimap_scale, xziel_hud_minimap_opacity); break;
	default: DRAW_STYLE(xziel_hud_fire_scale, xziel_hud_fire_opacity); break;
	}
#undef DRAW_STYLE

	Menu_DrawButton(-2, 2, "RESET LAYOUT", "Restore default mobile HUD positions and control styles.", Menu_HudEdit_Reset);
	Menu_DrawButton(-1, 3, "DONE", "Save HUD layout and return.", Menu_HudEdit_Done);
}
#endif


#ifdef __ANDROID__
static char *xziel_mobile_auto_rebuild_string;
static char *xziel_mobile_auto_knife_string;
static char *xziel_mobile_knife_visibility_string;
static char *xziel_mobile_unlimited_pistol_string;
static char *xziel_mobile_movement_string;
static char *xziel_modern_zombies_string;

static void Menu_Mobile_ToggleAutoRebuild(void)
{
	Cvar_SetValue("xziel_mobile_auto_rebuild",
		xziel_mobile_auto_rebuild.value >= 0.5f ? 0.0f : 1.0f);
}

static void Menu_Mobile_ToggleAutoKnife(void)
{
	Cvar_SetValue("xziel_mobile_auto_knife",
		xziel_mobile_auto_knife.value >= 0.5f ? 0.0f : 1.0f);
}

static char *xziel_mobile_track_fire_string;
static char *xziel_mobile_fire_rotation_string;

static void Menu_Mobile_ToggleTrackFireV23(void)
{
	Cvar_SetValue("xziel_mobile_track_fire",
		xziel_mobile_track_fire.value >= 0.5f ? 0.0f : 1.0f);
}

static void Menu_Mobile_ToggleFireRotationV23(void)
{
	Cvar_SetValue("xziel_mobile_fire_camera_rotation",
		xziel_mobile_fire_camera_rotation.value >= 0.5f ? 0.0f : 1.0f);
}

static void Menu_Mobile_ToggleModernZombiesV22(void)
{
	Cvar_SetValue("xziel_modern_zombies",
		xziel_modern_zombies.value >= 0.5f ? 0.0f : 1.0f);
}

static void Menu_Mobile_ToggleModernMovement(void)
{
    Cvar_SetValue("xziel_modern_movement",
        Cvar_VariableValue("xziel_modern_movement") >= 0.5f ? 0.0f : 1.0f);
}

static void Menu_Mobile_ToggleUnlimitedPistol(void)
{
    Cvar_SetValue("xziel_mobile_unlimited_pistol",
        xziel_mobile_unlimited_pistol.value >= 0.5f ? 0.0f : 1.0f);
}

static void Menu_Mobile_ToggleKnifeVisibility(void)
{
	Cvar_SetValue("xziel_mobile_knife_range_only",
		xziel_mobile_knife_range_only.value >= 0.5f ? 0.0f : 1.0f);
}

void Menu_MobileAim_Set(void)
{
	Menu_ResetMenuButtons();
	m_previous_state = m_mobile;
	m_state = m_mobileaim;
}

void Menu_MobileGyro_Set(void)
{
	Menu_ResetMenuButtons();
	m_previous_state = m_mobile;
	m_state = m_mobilegyro;
}

void Menu_MobileHud_Set(void)
{
	Menu_ResetMenuButtons();
	m_previous_state = m_mobile;
	m_state = m_mobilehud;
}

void Menu_MobileGameplay_Set(void)
{
	Menu_ResetMenuButtons();
	m_previous_state = m_mobile;
	m_state = m_mobilegameplay;
}


static char *xziel_mobile_ads_button_string;

static void Menu_Mobile_ToggleAdsButtonV21(void)
{
	Cvar_SetValue("xziel_mobile_ads_toggle",
		xziel_mobile_ads_toggle.value >= 0.5f ? 0.0f : 1.0f);
}

void Menu_MobileAim_Draw(void)
{
	int b=1, i=0;
	Menu_DrawCustomBackground(true);
	Menu_DrawMapPanel();
	Menu_DrawTitle("MOBILE AIM", MENU_COLOR_WHITE);

	xziel_mobile_ads_button_string =
		xziel_mobile_ads_toggle.value >= 0.5f ? "TOGGLE" : "HOLD";
	xziel_mobile_track_fire_string =
		xziel_mobile_track_fire.value >= 0.5f ? "TRACK" : "FIXED";
	xziel_mobile_fire_rotation_string =
		xziel_mobile_fire_camera_rotation.value >= 0.5f ? "ON" : "OFF";

	Menu_DrawButton(b++, i++, "ADS BUTTON", "Hold releases ADS with your finger. Toggle stays aimed until tapped again.", Menu_Mobile_ToggleAdsButtonV21);
	Menu_DrawOptionButton(b-1, xziel_mobile_ads_button_string);

	Menu_DrawButton(b++, i++, "FIRE BUTTON BEHAVIOR",
		"Track lets the FIRE / ADS+FIRE control follow your thumb inside the button while you aim and shoot. Fixed keeps the icon centered.",
		Menu_Mobile_ToggleTrackFireV23);
	Menu_DrawOptionButton(b-1, xziel_mobile_track_fire_string);

	Menu_DrawButton(b++, i++, "FIRE CAMERA ROTATION",
		"ON lets dragging FIRE / ADS+FIRE rotate the camera while the shot remains held, matching modern mobile FPS controls.",
		Menu_Mobile_ToggleFireRotationV23);
	Menu_DrawOptionButton(b-1, xziel_mobile_fire_rotation_string);

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
}

void Menu_MobileGyro_Draw(void)
{
	int idx = 0, row = 1;

	Menu_DrawCustomBackground(true);
	Menu_DrawTitle("MOBILE - GYROSCOPE", MENU_COLOR_WHITE);
	Menu_DrawMapPanel();
	Menu_Controls_SetStrings();

	Menu_DrawButton(row++, idx++, "GYRO MODE", "Off, Always On, or ADS Only.", Menu_Controls_ApplyGyroMode);
	Menu_DrawOptionButton(row-1, gyro_mode_string);

	Menu_DrawButton(row++, idx++, "HORIZONTAL", "Phone gyro horizontal/yaw sensitivity.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 0.5f, 30.0f, in_gyro_sensitivity_x, "in_gyro_sensitivity_x", false, true, 0.5f);

	Menu_DrawButton(row++, idx++, "VERTICAL", "Phone gyro vertical/pitch sensitivity.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 0.5f, 30.0f, in_gyro_sensitivity_y, "in_gyro_sensitivity_y", false, true, 0.5f);

	Menu_DrawButton(row++, idx++, "PHONE GYRO BOOST", "Extra Android phone-sensor multiplier.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 1.0f, 20.0f, xziel_mobile_gyro_boost, "xziel_mobile_gyro_boost", false, true, 0.5f);

	Menu_DrawButton(row++, idx++, "GYRO ADS SLOWDOWN", "Reduce gyro sensitivity while aiming down sights.", Menu_Controls_ApplyGyroZoomScaling);
	Menu_DrawOptionButton(row-1, gyro_zoom_scaling_string);

	Menu_DrawButton(-1, idx, "BACK", "Return to Mobile Settings.", Menu_Mobile_Set);
}

void Menu_MobileHud_Draw(void)
{
    int idx = 0, row = 1;

    Menu_DrawCustomBackground(true);
    Menu_DrawTitle("MOBILE - HUD & LAYOUT", MENU_COLOR_WHITE);
    Menu_DrawMapPanel();

    Menu_DrawButton(row++, idx++, "HUD SCALE", "Scale mobile action controls.", NULL);
    Menu_DrawOptionSlider(row-1, idx-1, 0.70f, 1.35f,
        xziel_mobile_hud_scale, "xziel_mobile_hud_scale", false, true, 0.05f);

    Menu_DrawButton(row++, idx++, "HUD OPACITY", "Opacity of mobile controls.", NULL);
    Menu_DrawOptionSlider(row-1, idx-1, 0.25f, 1.0f,
        xziel_mobile_hud_opacity, "xziel_mobile_hud_opacity", false, true, 0.05f);

    Menu_DrawButton(row++, idx++, "WEAPON STRIP SCALE", "Scale the weapon cards independently.", NULL);
    Menu_DrawOptionSlider(row-1, idx-1, 0.65f, 1.45f,
        xziel_hud_weapons_scale, "xziel_hud_weapons_scale", false, true, 0.05f);

    Menu_DrawButton(row++, idx++, "CUSTOM HUD",
        "Drag controls and the whole weapon strip to your preferred positions.", Menu_HudEdit_Set);

    Menu_DrawButton(-1, idx, "BACK", "Return to Mobile Settings.", Menu_Mobile_Set);
}

void Menu_MobileGameplay_Draw(void)
{
	int idx = 0, row = 1;

	Menu_DrawCustomBackground(true);
	Menu_DrawTitle("MOBILE - GAMEPLAY", MENU_COLOR_WHITE);
	Menu_DrawMapPanel();

	xziel_mobile_auto_rebuild_string =
		xziel_mobile_auto_rebuild.value >= 0.5f ? "ENABLED" : "DISABLED";
	xziel_mobile_auto_knife_string =
		xziel_mobile_auto_knife.value >= 0.5f ? "ENABLED" : "DISABLED";
	xziel_mobile_knife_visibility_string =
		xziel_mobile_knife_range_only.value >= 0.5f ? "IN RANGE" : "ALWAYS";
	xziel_mobile_unlimited_pistol_string =
		xziel_mobile_unlimited_pistol.value >= 0.5f ? "ENABLED" : "DISABLED";
	xziel_mobile_movement_string =
		Cvar_VariableValue("xziel_modern_movement") >= 0.5f ? "MODERN" : "CLASSIC";
	xziel_modern_zombies_string =
		xziel_modern_zombies.value >= 0.5f ? "MODERN" : "CLASSIC";

	Menu_DrawButton(row++, idx++, "MOVEMENT MODEL",
		"Modern: grounded FPS acceleration, braking, air steering and weighted jump. Classic restores legacy Quake movement.",
		Menu_Mobile_ToggleModernMovement);
	Menu_DrawOptionButton(row-1, xziel_mobile_movement_string);

	Menu_DrawButton(row++, idx++, "ZOMBIE MOTION",
		"Modern smooths zombie velocity/turn transitions while preserving NZ:P attack, crawl, barrier and death animation states.",
		Menu_Mobile_ToggleModernZombiesV22);
	Menu_DrawOptionButton(row-1, xziel_modern_zombies_string);

	Menu_DrawButton(row++, idx++, "JOYSTICK RESPONSE",
		"How quickly movement reaches full analog input. Sprint trigger still uses physical stick travel.",
		NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 0.50f, 2.00f,
		xziel_mobile_joystick_sensitivity, "xziel_mobile_joystick_sensitivity",
		false, true, 0.05f);

	Menu_DrawButton(row++, idx++, "ADS WALK SPEED",
		"Actual server ADS movement multiplier. NZ:P weapon weight still applies after this; 1.00 removes the old universal 50% ADS cap.",
		NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 0.35f, 1.75f,
		xziel_mobile_ads_move_sensitivity, "xziel_mobile_ads_move_sensitivity",
		false, true, 0.05f);

	Menu_DrawButton(row++, idx++, "SPRINT ACTIVATION HEIGHT",
		"Higher means drag farther above the joystick before native sprint starts.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 1.10f, 1.85f,
		xziel_mobile_sprint_zone, "xziel_mobile_sprint_zone", false, true, 0.05f);

	Menu_DrawButton(row++, idx++, "UNLIMITED PISTOL RESERVE",
		"Pistol magazines stay finite and still reload. Enables two ordinary weapons plus a protected pistol.",
		Menu_Mobile_ToggleUnlimitedPistol);
	Menu_DrawOptionButton(row-1, xziel_mobile_unlimited_pistol_string);

	Menu_DrawButton(row++, idx++, "AUTO REBUILD BARRIERS",
		"Automatically repair barricades while you remain in range.", Menu_Mobile_ToggleAutoRebuild);
	Menu_DrawOptionButton(row-1, xziel_mobile_auto_rebuild_string);

	Menu_DrawButton(row++, idx++, "AUTO KNIFE",
		"Automatically melee only when native NZ:P melee distance can reach the target.", Menu_Mobile_ToggleAutoKnife);
	Menu_DrawOptionButton(row-1, xziel_mobile_auto_knife_string);

	Menu_DrawButton(row++, idx++, "KNIFE BUTTON",
		"Show the manual knife button always or only at native melee distance.", Menu_Mobile_ToggleKnifeVisibility);
	Menu_DrawOptionButton(row-1, xziel_mobile_knife_visibility_string);

	Menu_DrawButton(-1, idx, "BACK", "Return to Mobile Settings.", Menu_Mobile_Set);
}
#endif
