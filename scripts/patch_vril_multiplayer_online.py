#!/usr/bin/env python3
"""Patch Vril's Android build with the Xziel Cloudflare datagram tunnel.

The original Quake/NZ:P datagram protocol remains authoritative. Only the SDL
UDP transport is intercepted for virtual 10.77.0.<player-slot> addresses while
an Xziel online room is active.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_vril_multiplayer_online.py <vril-root>")

root = Path(sys.argv[1])
source = root / "source"

def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit("Could not find " + label)
    return text.replace(old, new, 1)

# ---------------------------------------------------------------------------
# Main menu: use the formerly-grey cooperative slot as the room entry point.
# ---------------------------------------------------------------------------
main = source / "menu" / "menu_main.c"
text = main.read_text(encoding="utf-8")
resume_anchor = """#ifdef __ANDROID__
static qboolean Menu_XzielResumeExists(void)
"""
if "Menu_XzielMultiplayer" not in text:
    bridge = """#ifdef __ANDROID__
extern void Xziel_Android_OpenMultiplayer(void);

static void Menu_XzielMultiplayer(void)
{
    Xziel_Android_OpenMultiplayer();
}
#endif

"""
    text = replace_once(text, resume_anchor, bridge + resume_anchor,
                        "Android main-menu anchor")

old = """		Menu_DrawButton(1 + xziel_offset, xziel_offset, "SOLO", "Play Solo.", Menu_Solo);
		Menu_DrawGreyButton(2 + xziel_offset, "COOPERATIVE");

		Menu_DrawDivider(3 + xziel_offset);
"""
new = """		Menu_DrawButton(1 + xziel_offset, xziel_offset, "SOLO", "Play Solo.", Menu_Solo);
		Menu_DrawButton(2 + xziel_offset, 1 + xziel_offset, "MULTIPLAYER", "Create or join a private internet room.", Menu_XzielMultiplayer);

		Menu_DrawDivider(3 + xziel_offset);
"""
if old in text:
    text = text.replace(old, new, 1)

# Shift the following Android buttons down one logical selector slot.
text = text.replace(
    'Menu_DrawButton(3 + xziel_offset, 1 + xziel_offset, "CONFIGURATION"',
    'Menu_DrawButton(3 + xziel_offset, 2 + xziel_offset, "CONFIGURATION"',
    1)
text = text.replace(
    'Menu_DrawButton(4 + xziel_offset, 2 + xziel_offset, "CHARACTER BIOS"',
    'Menu_DrawButton(4 + xziel_offset, 3 + xziel_offset, "CHARACTER BIOS"',
    1)
text = text.replace(
    'Menu_DrawButton(5 + xziel_offset, 3 + xziel_offset, "CREDITS"',
    'Menu_DrawButton(5 + xziel_offset, 4 + xziel_offset, "CREDITS"',
    1)
text = text.replace(
    'Menu_DrawButton(6 + xziel_offset, 4 + xziel_offset, "QUIT GAME"',
    'Menu_DrawButton(6 + xziel_offset, 5 + xziel_offset, "QUIT GAME"',
    1)
main.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# Host frame: UI/network threads never call Cbuf directly. Android deposits
# commands and the game thread consumes them here before Cbuf_Execute().
# ---------------------------------------------------------------------------
host = source / "host.c"
text = host.read_text(encoding="utf-8")
platform_anchor = """#ifdef PLATFORM_SDL
extern qboolean sdl_running;
#endif
"""
online_decl = """#ifdef __ANDROID__
extern int Xziel_Android_OnlinePollCommand(char *out, int outSize);
extern void Xziel_Android_OnlineReportEngineState(int serverActive,
    int clientConnected, int signon, const char *map);
static double xziel_online_state_next;
#endif
"""
if "Xziel_Android_OnlinePollCommand" not in text:
    text = replace_once(text, platform_anchor, platform_anchor + online_decl,
                        "host Android declaration anchor")

execute_anchor = """// process console commands
	Cbuf_Execute ();
"""
execute_repl = """// process console commands
#ifdef __ANDROID__
	{
		char xziel_online_command[512];
		if (Xziel_Android_OnlinePollCommand(
			xziel_online_command, sizeof(xziel_online_command)))
			Cbuf_AddText(xziel_online_command);
	}
#endif
	Cbuf_Execute ();
#ifdef __ANDROID__
	if (Sys_FloatTime() >= xziel_online_state_next) {
		xziel_online_state_next = Sys_FloatTime() + 0.25;
		Xziel_Android_OnlineReportEngineState(
			sv.active ? 1 : 0,
			cls.state == ca_connected ? 1 : 0,
			cls.signon,
			sv.active ? sv.name : "");
	}
#endif
"""
if "char xziel_online_command[512]" not in text:
    text = replace_once(text, execute_anchor, execute_repl,
                        "host command execution anchor")
host.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# Cross-client game-audio evidence. The normal Vril sound packet is parsed and
# played first; Android only receives metadata afterwards, so this hook cannot
# synthesize or replace game audio.
# ---------------------------------------------------------------------------
cl_parse = source / "cl_parse.c"
text = cl_parse.read_text(encoding="utf-8")

cl_parse_include = '#include "nzportable_def.h"\n'
cl_parse_decl = """#ifdef __ANDROID__
extern int Xziel_Android_OnlineActive(void);
extern void Xziel_Android_CiSoundEvent(int ent, int channel, const char *name,
    float x, float y, float z);
#endif
"""
if "Xziel_Android_CiSoundEvent" not in text:
    text = replace_once(text, cl_parse_include, cl_parse_include + cl_parse_decl,
                        "cl_parse CI sound declaration")

# Online clients can receive serverinfo while still drawing the previous
# menu/world. CL_ClearState() frees map-owned GL textures, and the Con_Printf()
# calls immediately afterwards synchronously call SCR_UpdateScreen() while
# signon is incomplete. Gate redraws across that tiny unsafe window, then
# re-enable them once the remote loading screen owns rendering.
serverinfo_clear_anchor = r'''	Con_DPrintf ("Serverinfo packet received.\n");
	//Con_Printf ("Serverinfo packet received.\n");
//
// wipe the client_state_t struct
//
	CL_ClearState ();
'''
serverinfo_clear_repl = r'''	Con_DPrintf ("Serverinfo packet received.\n");
	//Con_Printf ("Serverinfo packet received.\n");
#ifdef __ANDROID__
	qboolean xziel_remote_loading_gate =
		Xziel_Android_OnlineActive() && !LoadingScreen_IsActive();
	if (xziel_remote_loading_gate)
		scr_disabled_for_loading = true;
#endif
//
// wipe the client_state_t struct
//
	CL_ClearState ();
'''
if "xziel_remote_loading_gate" not in text:
    text = replace_once(text, serverinfo_clear_anchor, serverinfo_clear_repl,
                        "remote serverinfo redraw gate")

# CL_KeepaliveMessage temporarily saves the current reliable net_message while
# precaching. The upstream scratch buffer is still hard-coded to 8192 even
# though NET_MAXMESSAGE is 16384. Large Zombies serverinfo messages can exceed
# 8192, so size the scratch buffer to the networking contract.
keepalive_old = r'''void CL_KeepaliveMessage (void)
{
	double	time;
	static double lastmsg;//BLUBSFIX, this was a float
	int		ret;
	sizebuf_t	old;
	byte		olddata[8192];
'''
keepalive_new = r'''void CL_KeepaliveMessage (void)
{
	double	time;
	static double lastmsg;//BLUBSFIX, this was a float
	int		ret;
	sizebuf_t	old;
	byte		olddata[NET_MAXMESSAGE];
'''
if "olddata[NET_MAXMESSAGE]" not in text:
    text = replace_once(text, keepalive_old, keepalive_new,
                        "CL_KeepaliveMessage network-sized scratch buffer")

sound_anchor = """    S_StartSound (ent, channel, cl.sound_precache[sound_num], pos, volume/255.0, attenuation);
}"""
sound_repl = """    S_StartSound (ent, channel, cl.sound_precache[sound_num], pos, volume/255.0, attenuation);
#ifdef __ANDROID__
    if (cl.sound_precache[sound_num]) {
        Xziel_Android_CiSoundEvent(
            ent, channel, cl.sound_precache[sound_num]->name,
            pos[0], pos[1], pos[2]);
    }
#endif
}"""
if "Xziel_Android_CiSoundEvent(" not in text[text.find("void CL_ParseStartSoundPacket"):]:
    text = replace_once(text, sound_anchor, sound_repl,
                        "CL_ParseStartSoundPacket CI evidence hook")

# Remote clients do not enter through Menu_SelectMap(), so they never call
# LoadingScreen_Begin() before CL_ClearState() frees map-owned textures.
# Derive the authoritative map name from model_precache[1] and activate the
# loading renderer before the first precache SCR_UpdateScreen().
remote_load_anchor = r'''  }

// precache sounds
'''
remote_load_repl = r'''  }

#ifdef __ANDROID__
	if (xziel_remote_loading_gate) {
		if (nummodels > 1 && model_precache[1][0]) {
			char xziel_remote_map[MAX_QPATH];
			COM_StripExtension(COM_SkipPath(model_precache[1]),
				xziel_remote_map);
			LoadingScreen_Begin(xziel_remote_map);
		} else {
			LoadingScreen_Begin("online");
		}
		scr_disabled_for_loading = false;
	}
#endif

// precache sounds
'''
if "xziel_remote_map" not in text:
    text = replace_once(text, remote_load_anchor, remote_load_repl,
                        "remote client loading-screen begin")

cl_parse.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# Remote-client gameplay state. A listen-server client can read sv_player
# directly, but a real network client has no local server edict. Replicate the
# two gameplay fields that input depends on, and make the remaining visual-only
# sv_player reads null-safe until their weapon offsets are mirrored explicitly.
# ---------------------------------------------------------------------------
defs = source / "nzportable_def.h"
dtext = defs.read_text(encoding="utf-8")
if "STAT_XZIEL_FACINGENEMY" not in dtext:
    dtext = replace_once(
        dtext,
        "#define\tSTAT_PRIGRENADES\t\t15\n",
        "#define\tSTAT_PRIGRENADES\t\t15\n#define STAT_XZIEL_FACINGENEMY   16\n",
        "remote facing-enemy stat")
if "STAT_XZIEL_MAXSPEED" not in dtext:
    dtext = replace_once(
        dtext,
        "#define STAT_XZIEL_W3RES         30\n",
        "#define STAT_XZIEL_W3RES         30\n#define STAT_XZIEL_MAXSPEED      31\n",
        "remote maxspeed stat")
defs.write_text(dtext, encoding="utf-8")

sv_main = source / "sv_main.c"
stext = sv_main.read_text(encoding="utf-8")
remote_stats_old = r'''\tMSG_WriteByte(msg, STAT_XZIEL_W3RES);
\tMSG_WriteLong(msg, (int)PR_GetEdictFloat(ent, "xziel_weapon3_reserve"));
'''
remote_stats_new = r'''\tMSG_WriteByte(msg, STAT_XZIEL_W3RES);
\tMSG_WriteLong(msg, (int)PR_GetEdictFloat(ent, "xziel_weapon3_reserve"));
\tMSG_WriteByte(msg, svc_updatestat);
\tMSG_WriteByte(msg, STAT_XZIEL_FACINGENEMY);
\tMSG_WriteLong(msg, (int)ent->v.facingenemy);
\tMSG_WriteByte(msg, svc_updatestat);
\tMSG_WriteByte(msg, STAT_XZIEL_MAXSPEED);
\tMSG_WriteLong(msg, (int)(ent->v.maxspeed * 100.0f));
'''
if "STAT_XZIEL_MAXSPEED);" not in stext:
    stext = replace_once(stext, remote_stats_old, remote_stats_new,
                         "remote gameplay stat replication")
sv_main.write_text(stext, encoding="utf-8")

client_h = source / "client.h"
htext = client_h.read_text(encoding="utf-8")
remote_helper_anchor = "void CL_BaseMove (usercmd_t *cmd);\n"
remote_helper_repl = """void CL_BaseMove (usercmd_t *cmd);
float CL_PlayerMoveSpeed (void);
qboolean CL_PlayerFacingEnemy (void);
"""
if "CL_PlayerMoveSpeed" not in htext:
    htext = replace_once(htext, remote_helper_anchor, remote_helper_repl,
                         "remote gameplay helper declarations")
client_h.write_text(htext, encoding="utf-8")

cl_input = source / "cl_input.c"
itext = cl_input.read_text(encoding="utf-8")
helper_anchor = """qboolean in_game;
float crosshair_opacity;
"""
helper_repl = r'''qboolean in_game;
float crosshair_opacity;

float CL_PlayerMoveSpeed (void)
{
\tif (sv.active && sv_player)
\t\treturn sv_player->v.maxspeed;
#ifdef __ANDROID__
\tif (cl.stats[STAT_XZIEL_MAXSPEED] > 0)
\t\treturn cl.stats[STAT_XZIEL_MAXSPEED] / 100.0f;
#endif
\t/* PlayerPreThink's normal non-beta walk speed. This only covers the first
\t   remote frame before the authoritative stat arrives. */
\treturn 190.0f;
}

qboolean CL_PlayerFacingEnemy (void)
{
\tif (sv.active && sv_player)
\t\treturn sv_player->v.facingenemy == 1;
#ifdef __ANDROID__
\treturn cl.stats[STAT_XZIEL_FACINGENEMY] != 0;
#else
\treturn false;
#endif
}
'''
if "float CL_PlayerMoveSpeed (void)" not in itext:
    itext = replace_once(itext, helper_anchor, helper_repl,
                         "remote gameplay helper implementations")
itext = itext.replace("(sv_player->v.facingenemy == 1)", "CL_PlayerFacingEnemy()")
itext = itext.replace("sv_player->v.maxspeed", "CL_PlayerMoveSpeed()")
# Restore the one intentional local-server read inside the helper after the
# global replacement above.
itext = itext.replace("return CL_PlayerMoveSpeed();\n#ifdef __ANDROID__",
                      "return sv_player->v.maxspeed;\n#ifdef __ANDROID__", 1)
cl_input.write_text(itext, encoding="utf-8")

inp = source / "input.c"
ptext = inp.read_text(encoding="utf-8")
ptext = ptext.replace("sv_player->v.facingenemy == 1", "CL_PlayerFacingEnemy()")
ptext = ptext.replace("sv_player->v.maxspeed", "CL_PlayerMoveSpeed()")
inp.write_text(ptext, encoding="utf-8")

cl_main = source / "cl_main.c"
mtext = cl_main.read_text(encoding="utf-8")
mtext = mtext.replace("move_limit = sv_player->v.maxspeed;",
                      "move_limit = CL_PlayerMoveSpeed();")
flash_old = r'''\t\t\t\tright_offset\t = sv_player->v.Flash_Offset[0];
\t\t\t\tup_offset\t\t = sv_player->v.Flash_Offset[1];
\t\t\t\tforward_offset \t = sv_player->v.Flash_Offset[2];
'''
flash_new = r'''\t\t\t\tif (sv.active && sv_player) {
\t\t\t\t\tright_offset\t = sv_player->v.Flash_Offset[0];
\t\t\t\t\tup_offset\t\t = sv_player->v.Flash_Offset[1];
\t\t\t\t\tforward_offset \t = sv_player->v.Flash_Offset[2];
\t\t\t\t} else {
\t\t\t\t\tright_offset = up_offset = forward_offset = 0;
\t\t\t\t}
'''
if "right_offset = up_offset = forward_offset = 0;" not in mtext:
    mtext = replace_once(mtext, flash_old, flash_new,
                         "remote muzzle offset null guard")
cl_main.write_text(mtext, encoding="utf-8")

view = source / "view.c"
vtext = view.read_text(encoding="utf-8")
ads_old = r'''\tif(cl.stats[STAT_ZOOM] == 1 || cl.stats[STAT_ZOOM] == 2)
\t{
\t\tADSOffset[0] = sv_player->v.ADS_Offset[0];
\t\tADSOffset[1] = sv_player->v.ADS_Offset[1];
\t\tADSOffset[2] = sv_player->v.ADS_Offset[2];
'''
ads_new = r'''\tif((cl.stats[STAT_ZOOM] == 1 || cl.stats[STAT_ZOOM] == 2) &&
\t\tsv.active && sv_player)
\t{
\t\tADSOffset[0] = sv_player->v.ADS_Offset[0];
\t\tADSOffset[1] = sv_player->v.ADS_Offset[1];
\t\tADSOffset[2] = sv_player->v.ADS_Offset[2];
'''
if "sv.active && sv_player)" not in vtext[vtext.find("vec3_t ADSOffset"):vtext.find("vec3_t ADSOffset")+600]:
    vtext = replace_once(vtext, ads_old, ads_new,
                         "remote ADS offset null guard")
view.write_text(vtext, encoding="utf-8")

particles = source / "render" / "r_particles.c"
rtext = particles.read_text(encoding="utf-8")
if "(sv.active && sv_player) ? sv_player->v.Flash_Size" not in rtext:
    rtext = replace_once(
        rtext,
        "        size = sv_player->v.Flash_Size;\n",
        "        size = (sv.active && sv_player) ? sv_player->v.Flash_Size : 5.0f;\n",
        "remote muzzle flash size null guard")
particles.write_text(rtext, encoding="utf-8")

# Make LoadingScreen_Begin() own the map-name storage instead of relying on
# Menu_SelectMap() to have set a borrowed pointer first. This keeps host/solo
# pretty names when the same map was selected locally and gives remote clients
# a valid stable map name for loading art, HUD labels and music.
loadscreen = source / "menu" / "menu_loadscreen.c"
ltext = loadscreen.read_text(encoding="utf-8")
loadscreen_globals = r'''char* 			map_loadname;
char* 			map_loadname_pretty;
'''
loadscreen_globals_repl = r'''char* 			map_loadname;
char* 			map_loadname_pretty;
static char		xziel_loading_map_name[MAX_QPATH];
'''
if "xziel_loading_map_name" not in ltext:
    ltext = replace_once(ltext, loadscreen_globals, loadscreen_globals_repl,
                         "loading screen owned map-name storage")

loadscreen_begin_new = r'''void LoadingScreen_Begin(const char *map_name)
{
	qboolean preserve_pretty =
		map_loadname && map_name && !Q_strcasecmp(map_loadname, map_name);

	if (!map_name || !map_name[0])
		map_name = "unknown";
	Q_strncpyz(xziel_loading_map_name, map_name,
		sizeof(xziel_loading_map_name));
	map_loadname = xziel_loading_map_name;
	if (!preserve_pretty)
		map_loadname_pretty = NULL;

	LoadingScreen_ClearProgress();
	loadingScreen = 1;
	loadscreeninit = false;
	lscreen_image = -1;
	lscreen_identifier[0] = '\\0';
	loading_waiting_for_input = menu_is_solo;
	loading_spawn_released = false;
	loading_precache_complete = false;
	loading_skip_key = -1;
	loadscreen_start_time = Sys_FloatTime();
	Music_PlayLoadingTrack(map_loadname);
}'''
if "preserve_pretty =" not in ltext:
    signature = "void LoadingScreen_Begin(const char *map_name)"
    begin = ltext.find(signature)
    if begin < 0:
        raise SystemExit("Could not find LoadingScreen_Begin signature")
    brace = ltext.find("{", begin)
    if brace < 0:
        raise SystemExit("Could not find LoadingScreen_Begin body")
    depth = 0
    finish = -1
    for i in range(brace, len(ltext)):
        if ltext[i] == "{":
            depth += 1
        elif ltext[i] == "}":
            depth -= 1
            if depth == 0:
                finish = i + 1
                break
    if finish < 0:
        raise SystemExit("Could not find LoadingScreen_Begin end")
    ltext = ltext[:begin] + loadscreen_begin_new + ltext[finish:]
loadscreen.write_text(ltext, encoding="utf-8")

# ---------------------------------------------------------------------------
# Online pause menu: gameplay continues while the overlay is open. Reuse the
# existing native scoreboard and expose only SETTINGS + QUIT MATCH. This runs
# after patch_vril_android.py, so the replacement deliberately preserves the
# mobile Solo Save & Exit path from that earlier patch.
# ---------------------------------------------------------------------------
pause = source / "menu" / "menu_pause.c"
text = pause.read_text(encoding="utf-8")

pause_include = '#include "menu_defs.h"\n'
pause_decls = r'''
#ifdef __ANDROID__
extern int Xziel_Android_OnlineActive(void);
extern void Xziel_Android_OnlineLeaveRoom(void);
extern void Xziel_Android_OnlinePauseVoice(int visible);
extern qboolean showscoreboard;
extern void HUD_EndScreen(void);
#endif
'''
if "Xziel_Android_OnlineLeaveRoom" not in text:
    text = replace_once(text, pause_include, pause_include + pause_decls,
                        "pause Android declarations")

def replace_c_function(src: str, signature: str, replacement: str) -> str:
    start = src.find(signature)
    if start < 0:
        raise SystemExit("Could not find " + signature)
    brace = src.find("{", start)
    if brace < 0:
        raise SystemExit("Could not find body for " + signature)
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
        raise SystemExit("Could not find end for " + signature)
    if end < len(src) and src[end] == ";":
        end += 1
    return src[:start] + replacement + src[end:]

pause_resume = r'''void Menu_Resume(void)
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
}'''
text = replace_c_function(text, "void Menu_Resume(void)", pause_resume)

configuration_old = "void Menu_Configuration(void) { Menu_Configuration_Set(); key_dest = key_menu_pause; };"
configuration_new = r'''void Menu_Configuration(void)
{
#ifdef __ANDROID__
	if (Xziel_Android_OnlineActive())
		Xziel_Android_OnlinePauseVoice(0);
#endif
	Menu_Configuration_Set();
	key_dest = key_menu_pause;
};'''
if configuration_old in text:
    text = text.replace(configuration_old, configuration_new, 1)

pause_set = r'''void Menu_Pause_Set (void)
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
}'''
text = replace_c_function(text, "void Menu_Pause_Set (void)", pause_set)

online_confirm = r'''
#ifdef __ANDROID__
static void Menu_Pause_OnlineQuitConfirm(void)
{
	menu_paus_submenu = 9;
	Menu_ResetMenuButtons();
	Menu_SetSound(MENU_SND_ENTER);
}
#endif
'''
if "Menu_Pause_OnlineQuitConfirm" not in text:
    anchor = "void Menu_Pause_Yes(void)\n"
    text = replace_once(text, anchor, online_confirm + "\n" + anchor,
                        "online quit confirm anchor")

pause_yes = r'''void Menu_Pause_Yes(void)
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
}'''
text = replace_c_function(text, "void Menu_Pause_Yes(void)", pause_yes)

pause_draw = r'''void Menu_Pause_Draw (void)
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
}'''
text = replace_c_function(text, "void Menu_Pause_Draw (void)", pause_draw)
pause.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# Proximity voice: push the rendered local player origin to Android. This is
# presentation-only and never changes movement, hit detection or net state.
# ---------------------------------------------------------------------------
cl_main = source / "cl_main.c"
text = cl_main.read_text(encoding="utf-8")

cl_include = '#include "nzportable_def.h"\n'
cl_voice_decl = """#ifdef __ANDROID__
extern void Xziel_Android_VoiceUpdatePosition(float x, float y, float z);
extern void Xziel_Android_CiRemoteEntity(int slot, float x, float y, float z,
    int frame, float yaw);
static double xziel_ci_avatar_next;
#endif
"""
if "Xziel_Android_VoiceUpdatePosition" not in text:
    text = replace_once(text, cl_include, cl_include + cl_voice_decl,
                        "cl_main voice include anchor")

cl_update_anchor = """	CL_RelinkEntities ();
	CL_UpdateTEnts ();

//
// bring the links up to date
//
"""
cl_update_repl = """	CL_RelinkEntities ();
	CL_UpdateTEnts ();

#ifdef __ANDROID__
	if (cl.viewentity > 0 && cl.viewentity < cl.num_entities) {
		entity_t *voice_listener = &cl_entities[cl.viewentity];
		Xziel_Android_VoiceUpdatePosition(
			voice_listener->origin[0],
			voice_listener->origin[1],
			voice_listener->origin[2]);
	}

	if (Sys_FloatTime() >= xziel_ci_avatar_next) {
		int xziel_slot;
		xziel_ci_avatar_next = Sys_FloatTime() + 0.20;
		for (xziel_slot = 1;
			 xziel_slot <= cl.maxclients && xziel_slot <= 4;
			 ++xziel_slot) {
			entity_t *avatar;
			if (xziel_slot == cl.viewentity)
				continue;
			if (!cl.scores || !cl.scores[xziel_slot - 1].name[0])
				continue;
			avatar = &cl_entities[xziel_slot];
			Xziel_Android_CiRemoteEntity(
				xziel_slot,
				avatar->origin[0], avatar->origin[1], avatar->origin[2],
				avatar->frame, avatar->angles[YAW]);
		}
	}
#endif

//
// bring the links up to date
//
"""
if "voice_listener = &cl_entities[cl.viewentity]" not in text:
    text = replace_once(text, cl_update_anchor, cl_update_repl,
                        "CL_ReadFromServer voice position anchor")

cl_main.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# Online map loading: CL_ParseServerInfo clears map-owned GL textures before it
# repeatedly calls SCR_UpdateScreen() to show precache progress. Online loading
# does not use LoadingScreen_IsWaiting() (that flag is the solo input gate), so
# the stock renderer would still draw the stale old world/HUD/menu in those
# frames and bind texture IDs that Mod_ClearAll() just freed. While any loading
# screen is active, render only the loading UI/progress until the new map has
# rebuilt its textures.
# ---------------------------------------------------------------------------
r_screen = source / "render" / "r_screen.c"
rtext = r_screen.read_text(encoding="utf-8")
old_loading_render = r'''	if (!LoadingScreen_IsWaiting()) {
		SCR_SetUpToDrawConsole ();
		V_RenderView ();
	}

	GL_Set2D ();

	if (!LoadingScreen_IsWaiting()) {
		//muff - to show FPS on screen
		SCR_DrawFPS ();
		HUD_Draw ();
		SCR_DrawConsole ();
		Menu_Draw ();
	}
'''
new_loading_render = r'''	if (!LoadingScreen_IsActive()) {
		SCR_SetUpToDrawConsole ();
		V_RenderView ();
	}

	GL_Set2D ();

	if (!LoadingScreen_IsActive()) {
		//muff - to show FPS on screen
		SCR_DrawFPS ();
		HUD_Draw ();
		SCR_DrawConsole ();
		Menu_Draw ();
	}
'''
if "Online loading must not render stale map textures" not in rtext:
    rtext = replace_once(rtext, old_loading_render, new_loading_render,
                         "online loading renderer guard")
    rtext = rtext.replace(
        "void SCR_UpdateScreen (void)\n{",
        "void SCR_UpdateScreen (void)\n{\n\t/* Online loading must not render stale map textures. */",
        1)
r_screen.write_text(rtext, encoding="utf-8")

# ---------------------------------------------------------------------------
# SDL UDP: virtual internet peers are 10.77.0.<slot>. OS UDP remains untouched
# for normal solo/LAN operation and for local socket allocation/port identity.
# ---------------------------------------------------------------------------
udp = source / "platform" / "sdl" / "net_udp_sdl.c"
text = udp.read_text(encoding="utf-8")
include_anchor = '#include <unistd.h>\n\n'
decls = r'''#ifdef __ANDROID__
extern int Xziel_Android_OnlineActive(void);
extern int Xziel_Android_GameHasPacket(int localPort);
extern int Xziel_Android_GameSend(const unsigned char *data, int len,
    int destinationSlot, int sourcePort, int destinationPort);
extern int Xziel_Android_GamePoll(int localPort, unsigned char *out, int maxLen,
    int *sourceSlot, int *sourcePort);

#define XZIEL_VIRTUAL_NET 0x0A4D0000u

static int Xziel_SocketPort(int socket_fd)
{
    struct sockaddr_in address;
    socklen_t len = sizeof(address);
    if (getsockname(socket_fd, (struct sockaddr *)&address, &len) == -1)
        return 0;
    return ntohs(address.sin_port);
}

static int Xziel_VirtualSlot(const struct qsockaddr *addr)
{
    unsigned int host;
    if (!addr || addr->sa_family != AF_INET)
        return 0;
    host = ntohl(((const struct sockaddr_in *)addr)->sin_addr.s_addr);
    if ((host & 0xFFFFFF00u) != XZIEL_VIRTUAL_NET)
        return 0;
    host &= 0xFFu;
    return (host >= 1u && host <= 4u) ? (int)host : 0;
}

static void Xziel_SetVirtualAddr(struct qsockaddr *addr, int slot, int port)
{
    struct sockaddr_in *internet = (struct sockaddr_in *)addr;
    memset(addr, 0, sizeof(*addr));
    internet->sin_family = AF_INET;
    internet->sin_addr.s_addr = htonl(XZIEL_VIRTUAL_NET | (unsigned int)slot);
    internet->sin_port = htons((unsigned short)port);
}
#endif

'''
if "XZIEL_VIRTUAL_NET" not in text:
    text = replace_once(text, include_anchor, include_anchor + decls,
                        "UDP include anchor")

old_check = r'''int UDP_CheckNewConnections (void)
{
	char buf[4096];
	
	if (net_acceptsocket == -1)
		return -1;

	if (recvfrom(net_acceptsocket, buf, 4096, MSG_PEEK, NULL, NULL) > 0)
		return net_acceptsocket;
		
	return -1;
}'''
new_check = r'''int UDP_CheckNewConnections (void)
{
	char buf[4096];

	if (net_acceptsocket == -1)
		return -1;

#ifdef __ANDROID__
	if (Xziel_Android_OnlineActive()) {
		int local_port = Xziel_SocketPort(net_acceptsocket);
		if (local_port > 0 && Xziel_Android_GameHasPacket(local_port))
			return net_acceptsocket;
	}
#endif

	if (recvfrom(net_acceptsocket, buf, 4096, MSG_PEEK, NULL, NULL) > 0)
		return net_acceptsocket;

	return -1;
}'''
text = replace_once(text, old_check, new_check, "UDP_CheckNewConnections")

old_read = r'''int UDP_Read (int socket, byte *buf, int len, struct qsockaddr *addr)
{
	int addrlen = sizeof (struct qsockaddr);
	int ret;

	ret = recvfrom(socket, (char *)buf, len, 0, (struct sockaddr *)addr, (socklen_t*)&addrlen);
	if (ret == -1 )
		return 0;
	return ret;
}'''
new_read = r'''int UDP_Read (int socket, byte *buf, int len, struct qsockaddr *addr)
{
	int addrlen = sizeof (struct qsockaddr);
	int ret;

#ifdef __ANDROID__
	if (Xziel_Android_OnlineActive()) {
		int local_port = Xziel_SocketPort(socket);
		int source_slot = 0;
		int source_port = 0;
		if (local_port > 0) {
			ret = Xziel_Android_GamePoll(local_port, buf, len,
				&source_slot, &source_port);
			if (ret > 0 && source_slot >= 1 && source_slot <= 4) {
				Xziel_SetVirtualAddr(addr, source_slot, source_port);
				return ret;
			}
		}
	}
#endif

	ret = recvfrom(socket, (char *)buf, len, 0,
		(struct sockaddr *)addr, (socklen_t*)&addrlen);
	if (ret == -1 )
		return 0;
	return ret;
}'''
text = replace_once(text, old_read, new_read, "UDP_Read")

old_write = r'''int UDP_Write (int socket, byte *buf, int len, struct qsockaddr *addr)
{
	int ret;

	ret = sendto (socket, (const char *)buf, len, 0, (struct sockaddr *)addr, sizeof(struct qsockaddr));
	if (ret == -1 )
		return 0;
	return ret;
}'''
new_write = r'''int UDP_Write (int socket, byte *buf, int len, struct qsockaddr *addr)
{
	int ret;

#ifdef __ANDROID__
	if (Xziel_Android_OnlineActive()) {
		int destination_slot = Xziel_VirtualSlot(addr);
		if (destination_slot) {
			int source_port = Xziel_SocketPort(socket);
			int destination_port =
				ntohs(((struct sockaddr_in *)addr)->sin_port);
			if (source_port > 0 &&
				Xziel_Android_GameSend(buf, len, destination_slot,
					source_port, destination_port))
				return len;
			// Keep Vril's normal UDP error contract. A rejected tunnel packet
			// must be -1; returning 0 makes Datagram_SendMessage mark reliable
			// signon data as sent even though Java/Worker dropped it.
			return -1;
		}
	}
#endif

	ret = sendto (socket, (const char *)buf, len, 0,
		(struct sockaddr *)addr, sizeof(struct qsockaddr));
	if (ret == -1 )
		return 0;
	return ret;
}'''
text = replace_once(text, old_write, new_write, "UDP_Write")
udp.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# Bounded native datagram diagnostics for Android CI. This does not alter
# routing or packet contents; it proves whether post-connect packets are
# rejected by address validation or fail before the ACK write.
# ---------------------------------------------------------------------------
dgrm = source / "platform" / "sdl" / "net_dgrm.c"
dtext = dgrm.read_text(encoding="utf-8")

d_include = '#include "net_dgrm.h"\n'
d_diag_decl = r'''#ifdef __ANDROID__
#include <android/log.h>
static int xziel_dgrm_trace_count;
#endif
'''
if "xziel_dgrm_trace_count" not in dtext:
    dtext = replace_once(dtext, d_include, d_include + d_diag_decl,
                         "Datagram Android diagnostics include")

d_addr_old = r'''		if (sfunc.AddrCompare(&readaddr, &sock->addr) != 0)
		{
#ifdef DEBUG
			Con_DPrintf("Forged packet received\n");
			Con_DPrintf("Expected: %s\n", StrAddr (&sock->addr));
			Con_DPrintf("Received: %s\n", StrAddr (&readaddr));
#endif
			continue;
		}
'''
d_addr_new = r'''		{
			int xziel_addr_compare = sfunc.AddrCompare(&readaddr, &sock->addr);
#ifdef __ANDROID__
			if (xziel_dgrm_trace_count < 32) {
				struct sockaddr_in *expected =
					(struct sockaddr_in *)&sock->addr;
				struct sockaddr_in *received =
					(struct sockaddr_in *)&readaddr;
				unsigned int xziel_header = BigLong(packetBuffer.length);
				unsigned int xziel_flags =
					xziel_header & (~NETFLAG_LENGTH_MASK);
				unsigned int xziel_declared =
					xziel_header & NETFLAG_LENGTH_MASK;
				unsigned int xziel_sequence = BigLong(packetBuffer.sequence);
				__android_log_print(ANDROID_LOG_INFO, "XzielNet",
					"DGRM_RX bytes=%u declared=%u flags=0x%08x seq=%u "
					"expected=%u.%u.%u.%u:%u got=%u.%u.%u.%u:%u cmp=%d",
					length, xziel_declared, xziel_flags, xziel_sequence,
					(ntohl(expected->sin_addr.s_addr) >> 24) & 0xff,
					(ntohl(expected->sin_addr.s_addr) >> 16) & 0xff,
					(ntohl(expected->sin_addr.s_addr) >> 8) & 0xff,
					ntohl(expected->sin_addr.s_addr) & 0xff,
					ntohs(expected->sin_port),
					(ntohl(received->sin_addr.s_addr) >> 24) & 0xff,
					(ntohl(received->sin_addr.s_addr) >> 16) & 0xff,
					(ntohl(received->sin_addr.s_addr) >> 8) & 0xff,
					ntohl(received->sin_addr.s_addr) & 0xff,
					ntohs(received->sin_port),
					xziel_addr_compare);
				xziel_dgrm_trace_count++;
			}
#endif
			if (xziel_addr_compare != 0)
			{
#ifdef DEBUG
				Con_DPrintf("Forged packet received\n");
				Con_DPrintf("Expected: %s\n", StrAddr (&sock->addr));
				Con_DPrintf("Received: %s\n", StrAddr (&readaddr));
#endif
				continue;
			}
		}
'''
if "DGRM_RX bytes=" not in dtext:
    dtext = replace_once(dtext, d_addr_old, d_addr_new,
                         "Datagram address-compare diagnostics")

d_ack_old = r'''			packetBuffer.length = BigLong(NET_HEADERSIZE | NETFLAG_ACK);
			packetBuffer.sequence = BigLong(sequence);
			sfunc.Write (sock->socket, (byte *)&packetBuffer, NET_HEADERSIZE, &readaddr);
'''
d_ack_new = r'''			int xziel_ack_result;
			packetBuffer.length = BigLong(NET_HEADERSIZE | NETFLAG_ACK);
			packetBuffer.sequence = BigLong(sequence);
			xziel_ack_result =
				sfunc.Write (sock->socket, (byte *)&packetBuffer,
					NET_HEADERSIZE, &readaddr);
#ifdef __ANDROID__
			if (xziel_dgrm_trace_count < 32) {
				__android_log_print(ANDROID_LOG_INFO, "XzielNet",
					"DGRM_ACK seq=%u write=%d", sequence, xziel_ack_result);
				xziel_dgrm_trace_count++;
			}
#endif
'''
if "DGRM_ACK seq=" not in dtext:
    dtext = replace_once(dtext, d_ack_old, d_ack_new,
                         "Datagram ACK diagnostics")

dgrm.write_text(dtext, encoding="utf-8")

print("Xziel multiplayer internet tunnel patch applied.")
