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
/* MAIN MENU */
qboolean in_submenu;

#ifdef __ANDROID__
extern void Xziel_Android_OpenMultiplayer(void);

static void Menu_XzielMultiplayer(void)
{
    Xziel_Android_OpenMultiplayer();
}
#endif

#ifdef __ANDROID__
static qboolean Menu_XzielResumeExists(void)
{
	char path[MAX_OSPATH + 1];
	snprintf(path, sizeof(path), "%s/xziel_resume.sav", com_gamedir);
	return Sys_FileTime(path) != -1;
}

static void Menu_XzielResume(void)
{
	Cbuf_AddText("load xziel_resume\n");
	Cbuf_Execute();
	key_dest = key_game;
	m_state = m_none;
}
#endif

void Menu_Solo(void) { menu_is_solo = true; Menu_StockMaps_Set(); }
void Menu_Quit(void) { key_dest = key_console; Host_Quit_f(); }
void Menu_EnterSubMenu(void) { Menu_ResetMenuButtons(); in_submenu = true; }
void Menu_ExitSubMenu(void) { in_submenu = false; Menu_ResetMenuButtons(); }

/*
===============
Menu_Main_Set
===============
*/
void Menu_Main_Set (void)
{
	loadingScreen = 0;
	loadscreeninit = false;

	Menu_LoadPics();
	Menu_ResetMenuButtons();
	Menu_SetSound(MENU_SND_ENTER);
	if (key_dest != key_menu) {
		Cbuf_AddText("cd playstring tensioned_by_the_damned 1\n");
	}

	key_dest = key_menu;
	m_previous_state = 0;
	m_state = m_main;
	loadingScreen = 0;
}

/*
===============
Menu_Main_Draw
===============
*/
void Menu_Main_Draw (void)
{
	// Background
	Menu_DrawCustomBackground (true);

	// Header
	Menu_DrawTitle ("MAIN MENU", MENU_COLOR_WHITE);

	// Version String
	Menu_DrawBuildDate();

	if (!in_submenu) {
#ifdef __ANDROID__
		int xziel_offset = 0;
		if (Menu_XzielResumeExists()) {
			Menu_DrawButton(1, 0, "RESUME GAME", "Resume your saved Solo match.", Menu_XzielResume);
			xziel_offset = 1;
		}
		Menu_DrawButton(1 + xziel_offset, xziel_offset, "SOLO", "Play Solo.", Menu_Solo);
		Menu_DrawButton(2 + xziel_offset, 1 + xziel_offset, "MULTIPLAYER", "Create or join a private internet room.", Menu_XzielMultiplayer);

		Menu_DrawDivider(3 + xziel_offset);

		Menu_DrawButton(3 + xziel_offset, 2 + xziel_offset, "CONFIGURATION", "Tweak Game Related Options", Menu_Configuration_Set);
		Menu_DrawButton(4 + xziel_offset, 3 + xziel_offset, "CHARACTER BIOS", "View Character Bios", Menu_Bios_Set);

		Menu_DrawDivider(5 + xziel_offset);

		Menu_DrawButton(5 + xziel_offset, 4 + xziel_offset, "CREDITS", "NZ:P Team + Special Thanks", Menu_Credits_Set);

		Menu_DrawDivider(6 + xziel_offset);

		Menu_DrawButton(6 + xziel_offset, 5 + xziel_offset, "QUIT GAME", "Return to Home Screen", Menu_EnterSubMenu);
#else
		Menu_DrawButton(1, 0, "SOLO", "Play Solo.", Menu_Solo);
		Menu_DrawGreyButton(2, "COOPERATIVE");

		Menu_DrawDivider(3);

		Menu_DrawButton(3, 1, "CONFIGURATION", "Tweak Game Related Options", Menu_Configuration_Set);
		Menu_DrawButton(4, 2, "CHARACTER BIOS", "View Character Bios", Menu_Bios_Set);

		Menu_DrawDivider(5);

		Menu_DrawButton(5, 3, "CREDITS", "NZ:P Team + Special Thanks", Menu_Credits_Set);

		Menu_DrawDivider(6);

		Menu_DrawButton(6, 4, "QUIT GAME", "Return to Home Screen", Menu_EnterSubMenu);
#endif

		Menu_DrawSocialBadge (1, MENU_SOC_YOUTUBE);
		Menu_DrawSocialBadge (2, MENU_SOC_BLUESKY);
		Menu_DrawSocialBadge (3, MENU_SOC_PATREON);
		Menu_DrawSocialBadge (4, MENU_SOC_DOCS);
	} else {
		Menu_DrawGreyButton(1, "SOLO");
		Menu_DrawGreyButton(2, "COOPERATIVE");
		Menu_DrawDivider(3);
		Menu_DrawGreyButton(3, "CONFIGURATION");
		Menu_DrawGreyButton(4, "CHARACTER BIOS");
		Menu_DrawDivider(5);
		Menu_DrawGreyButton(5, "CREDITS");
		Menu_DrawDivider(6);
		Menu_DrawGreyButton(6, "QUIT GAME");

		Menu_DrawSocialBadge (1, MENU_SOC_YOUTUBE);
		Menu_DrawSocialBadge (2, MENU_SOC_BLUESKY);
		Menu_DrawSocialBadge (3, MENU_SOC_PATREON);
		Menu_DrawSocialBadge (4, MENU_SOC_DOCS);

		// Draw Sub Menu
    	Menu_DrawSubMenu("Are you sure you want to quit?", "You will lose any progress that you have made.");

		Menu_DrawButton (7, 0, "GET ME OUTTA HERE!", "", Menu_Quit);
		Menu_DrawButton (8, 1, "I WILL PERSEVERE", "", Menu_ExitSubMenu);
	}
}
