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

#ifdef __ANDROID__
extern int Xziel_Android_OnlineActive(void);
extern void Xziel_Android_OnlineLeaveRoom(void);
extern void Xziel_Android_OnlinePauseVoice(int visible);
extern qboolean showscoreboard;
extern void HUD_EndScreen(void);
#endif

#ifdef __ANDROID__
extern qboolean xziel_mobile_resume_countdown;
extern double xziel_mobile_resume_countdown_end;
void Xziel_BeginMobileResumeCountdown(void);
#endif

//=============================================================================
/* PAUSE MENU */

// Waypoint saving in pause screen
extern cvar_t 	waypoint_mode;
int 			menu_paus_submenu;

void Menu_Resume(void)
{
	key_dest = key_game;
	m_state = m_none;
	m_previous_state = m_state;
#ifdef __ANDROID__
	if (Xziel_Android_OnlineActive()) {
		Xziel_Android_OnlinePauseVoice(0);
	} else if (sv.active && svs.maxclients == 1) {
		Xziel_BeginMobileResumeCountdown();
		return;
	}
#endif
	Music_Resume();
}
void Menu_Configuration(void)
{
#ifdef __ANDROID__
	if (Xziel_Android_OnlineActive())
		Xziel_Android_OnlinePauseVoice(0);
#endif
	Menu_Configuration_Set();
	key_dest = key_menu_pause;
};
void Menu_Pause_EnterSubMenu(void)
{
	menu_paus_submenu = current_menu.cursor;
	Menu_ResetMenuButtons();
    Menu_SetSound(MENU_SND_ENTER);
}


#ifdef __ANDROID__
static void Menu_Pause_OnlineQuitConfirm(void)
{
	menu_paus_submenu = 9;
	Menu_ResetMenuButtons();
	Menu_SetSound(MENU_SND_ENTER);
}
#endif

void Menu_Pause_Yes(void)
{
#ifdef __ANDROID__
	if (Xziel_Android_OnlineActive() && menu_paus_submenu == 9) {
		Xziel_Android_OnlineLeaveRoom();
		menu_paus_submenu = 0;
		Menu_ExitMap();
		return;
	}
#endif

	if (menu_paus_submenu == 1) {
		// User is restarting the map.
		menu_paus_submenu = 0;
		key_dest = key_game;
		m_state = m_none;
		m_previous_state = m_state;

		if (music_paused)
			Music_Resume();

		SV_RestartServer ();
	} else if (menu_paus_submenu ==
#ifdef __ANDROID__
		4
#else
		3
#endif
	) {
		// User is returning to Main Menu.
		menu_paus_submenu = 0;
		Menu_ExitMap();
	}

	Menu_Pause_EnterSubMenu();
}

void Menu_Pause_No (void)
{
    Menu_Pause_Set();
}

/*
===============
Menu_Pause_Set
===============
*/
void Menu_Pause_Set (void)
{
	Menu_ResetMenuButtons();
#ifdef __ANDROID__
	if (!Xziel_Android_OnlineActive()) {
		S_StopAllSounds(true);
		Music_Pause();
	}
#else
	S_StopAllSounds(true);
	Music_Pause();
#endif
	Menu_SetSound(MENU_SND_ENTER);

	menu_paus_submenu = 0;
	loadingScreen = 0;
	loadscreeninit = false;
	key_dest = key_menu_pause;
	m_state = m_pause;
	m_previous_state = m_state;
#ifdef __ANDROID__
	// Solo still freezes exactly as before. Online maxclients > 1 keeps
	// simulation and networking running behind this menu.
	if (Xziel_Android_OnlineActive()) {
		Xziel_Android_OnlinePauseVoice(1);
	} else if (sv.active && svs.maxclients == 1) {
		sv.paused = true;
	}
#endif
}

/*
===============
Menu_Pause_Draw
===============
*/

#ifdef __ANDROID__
static void Menu_Pause_SaveAndExit(void)
{
	if (!sv.active || svs.maxclients != 1 || cl.stats[STAT_HEALTH] <= 0)
		return;
	Cbuf_AddText("save xziel_resume\n");
	Cbuf_Execute();
	sv.paused = false;
	Menu_ExitMap();
}
#endif

void Menu_Pause_Draw (void)
{
#ifdef __ANDROID__
	if (Xziel_Android_OnlineActive()) {
		qboolean old_scoreboard = showscoreboard;

		Menu_DrawCustomBackground (true);
		Menu_DrawTitle ("ONLINE MATCH", MENU_COLOR_WHITE);

		// Native NZ:P scoreboard: Score, Kills, Downs, Revives,
		// Headshots and ping for every connected player.
		showscoreboard = true;
		HUD_EndScreen();
		showscoreboard = old_scoreboard;

		if (menu_paus_submenu == 0) {
			Menu_DrawButton (1, 0, "SETTINGS",
				"Adjust controls, audio and video.", Menu_Configuration);
			Menu_DrawButton (2, 1, "QUIT MATCH",
				"Leave this online match.", Menu_Pause_OnlineQuitConfirm);
		} else {
			Menu_DrawGreyButton (1, "SETTINGS");
			Menu_DrawGreyButton (2, "QUIT MATCH");
			Menu_DrawSubMenu("Leave online match?",
				"The other players will keep playing.");
			Menu_DrawButton (7, 0, "QUIT MATCH", "", Menu_Pause_Yes);
			Menu_DrawButton (8, 1, "STAY", "", Menu_Pause_No);
		}
		return;
	}
#endif

	// Existing Solo pause menu.
	Menu_DrawCustomBackground (true);
	Menu_DrawTitle ("PAUSED", MENU_COLOR_WHITE);

	if (menu_paus_submenu == 0) {
		Menu_DrawButton (1, 0, "RESUME CARNAGE", "Return to Game.", Menu_Resume);
		Menu_DrawButton (2, 1, "RESTART LEVEL",
			"Tough luck? Give things another go.", Menu_Pause_EnterSubMenu);
		Menu_DrawButton (3, 2, "OPTIONS",
			"Tweak Game related Options.", Menu_Configuration);
#ifdef __ANDROID__
		Menu_DrawButton (4, 3, "SAVE & EXIT",
			"Save current Solo state and return to Main Menu.", Menu_Pause_SaveAndExit);
		Menu_DrawButton (5, 4, "EXIT TO MENU",
			"Return to Main Menu without saving.", Menu_Pause_EnterSubMenu);
#else
		Menu_DrawButton (4, 3, "END GAME",
			"Return to Main Menu.", Menu_Pause_EnterSubMenu);
#endif
	} else {
		Menu_DrawGreyButton (1, "RESUME CARNAGE");
		Menu_DrawGreyButton (2, "RESTART LEVEL");
		Menu_DrawGreyButton (3, "OPTIONS");
#ifdef __ANDROID__
		Menu_DrawGreyButton (4, "SAVE & EXIT");
		Menu_DrawGreyButton (5, "EXIT TO MENU");
#else
		Menu_DrawGreyButton (4, "END GAME");
#endif

		if (menu_paus_submenu == 1) {
			Menu_DrawSubMenu("Are you sure you want to restart?",
				"You will lose any progress that you have made.");
		} else if (menu_paus_submenu ==
#ifdef __ANDROID__
			4
#else
			3
#endif
		) {
			Menu_DrawSubMenu("Are you sure you want to quit?",
				"You will lose any unsaved progress.");
		}

		Menu_DrawButton (7, 0, "GET ME OUTTA HERE!", "", Menu_Pause_Yes);
		Menu_DrawButton (8, 1, "I WILL PERSEVERE", "", Menu_Pause_No);
	}
}
