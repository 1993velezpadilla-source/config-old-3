#!/usr/bin/env python3
"""Native, touchscreen-accessible Sanctum developer tools in Pause menu.

Opt-in ONLY for the authored Tripo Android build. Never enables cheats for
co-op games and never changes a regular NZ:P APK or other church profiles.
"""
from pathlib import Path
import sys
if len(sys.argv)!=2:
    raise SystemExit("usage: patch_vril_sanctum_dev_menu.py <vril-root>")
p=Path(sys.argv[1])/"source/menu/menu_pause.c"
s=p.read_text(encoding="utf-8")
a="void Menu_Pause_No (void)"
insertion=r'''
/* XZIEL_SANCTUM_DEVMENU - in-engine, tap-able and build-profile isolated. */
static void Xziel_DevFPS(void)
{
    Cvar_SetValue("show_fps", Cvar_VariableValue("show_fps") >= 0.5f ? 0 : 1);
}
static void Xziel_DevNoClip(void)
{
    /* Never allow convenience developer cheats to be sent to a co-op server. */
    if (sv.active && svs.maxclients == 1)
        Cbuf_AddText("noclip\n");
    else
        Con_Printf("XZIEL: noclip is local solo only\n");
}
static void Xziel_DevGod(void)
{
    if (sv.active && svs.maxclients == 1)
        Cbuf_AddText("god\n");
    else
        Con_Printf("XZIEL: god mode is local solo only\n");
}
'''
if s.count(a)!=1:raise RuntimeError("Upstream pause menu changed: function insertion")
s=s.replace(a,insertion+"\n"+a,1)
a='\t\tMenu_DrawButton (4, 3, "END GAME", "Return to Main Menu.", Menu_Pause_EnterSubMenu);'
b=a+'\n\t\tMenu_DrawButton (5, 4, "DEVELOPER TOOLS", "Local map inspection and profiling.", Menu_Pause_EnterSubMenu);'
if s.count(a)!=1:raise RuntimeError("Upstream pause button layout changed")
s=s.replace(a,b,1)
a='\t} else {\n\t\tMenu_DrawGreyButton (1,"RESUME CARNAGE");'
b='''	} else if (menu_paus_submenu == 4) {
		Menu_DrawTitle("XZIEL DEVELOPER TOOLS", MENU_COLOR_WHITE);
		Menu_DrawButton(1, 0, "SHOW FPS", "Toggle in-game frame counter.", Xziel_DevFPS);
		Menu_DrawButton(2, 1, "NOCLIP (SOLO)", "Local movement/collision inspection.", Xziel_DevNoClip);
		Menu_DrawButton(3, 2, "GOD MODE (SOLO)", "Local zombie encounter inspection.", Xziel_DevGod);
		Menu_DrawButton(4, 3, "DEVELOPER CONSOLE", "Engine console for advanced debugging.", Con_ToggleConsole_f);
		Menu_DrawButton(5, 4, "BACK TO PAUSE", "Return to main pause menu.", Menu_Pause_Set);
	} else {
		Menu_DrawGreyButton (1,"RESUME CARNAGE");'''
if s.count(a)!=1:raise RuntimeError("Upstream pause submenu changed")
s=s.replace(a,b,1)
assert s.count("XZIEL_SANCTUM_DEVMENU")==1
assert "svs.maxclients == 1" in s
p.write_text(s,encoding="utf-8")
print("XZIEL_SANCTUM_NATIVE_DEVMENU_GREEN")
