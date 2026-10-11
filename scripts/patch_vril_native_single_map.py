#!/usr/bin/env python3
"""Apply single-map and developer UI to the *native Vril C menus*.

The QuakeC menu source is not used by the SDL/Vril Android renderer.
This script runs after every other native C patch and fails on upstream drift.
"""
from pathlib import Path
import re
import sys

if len(sys.argv) != 3 or not re.fullmatch(r"[A-Za-z0-9_-]+", sys.argv[2]):
    raise SystemExit("usage: patch_vril_native_single_map.py <vril-root> <map-id>")

root = Path(sys.argv[1])
menu = root / "source/menu"
single_map = sys.argv[2]

def replace_once(s, old, new, label):
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"Native Vril API drift: {label}, expected 1, found {n}")
    return s.replace(old, new, 1)

def replace_function(s, signature, new):
    start = s.find(signature)
    if start < 0:
        raise SystemExit("Missing native function " + signature)
    left = s.find("{", start)
    depth = 0
    right = -1
    for i in range(left, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                right = i+1
                break
    if right < 0:
        raise SystemExit("Unbalanced native function " + signature)
    return s[:start] + new + s[right:]

def read(name):
    return (menu/name).read_text(encoding="utf-8")

def write(name, value):
    (menu/name).write_text(value, encoding="utf-8")

# Do not display eight stock-map entries when the APK contains one BSP.
s = read("menu_helper.c")
s = replace_once(s,
    "num_stock_maps = sizeof(stock_maps)/sizeof(stock_maps[0]);",
    "num_stock_maps = 1; // XZIEL SINGLE MAP: only the first (ndu) map.",
    "native stock-map count")
write("menu_helper.c", s)

# Override *native C* main menu, not QuakeC menu/menu_main.qc.
s = read("menu_main.c")
s = replace_once(s,
    "void Menu_Solo(void) { menu_is_solo = true; Menu_StockMaps_Set(); }",
    'void Menu_Solo(void) { menu_is_solo = true; Map_SetDefaultValues(); current_selected_bsp = "' + single_map + '"; Menu_Lobby_Set(); }',
    "native solo route")
s = replace_function(s, "void Menu_Main_Draw (void)", r'''void Menu_Main_Draw (void)
{
    Menu_DrawCustomBackground(true);
    Menu_DrawTitle("ZOMBIES NATIVE DEV", MENU_COLOR_WHITE);
    if (!in_submenu) {
        Menu_DrawButton(1, 0, "PLAY NACHT", "One-map native Vril build.", Menu_Solo);
        Menu_DrawGreyButton(2, "COOPERATIVE (UNAVAILABLE)");
        Menu_DrawDivider(3);
        Menu_DrawButton(3, 1, "SETTINGS", "Video, sound, gyro and touch.", Menu_Configuration_Set);
        Menu_DrawButton(4, 2, "CREDITS", "Original NZ:P and Vril team.", Menu_Credits_Set);
        Menu_DrawButton(5, 3, "EXIT", "Close Android prototype.", Menu_EnterSubMenu);
    } else {
        Menu_DrawGreyButton(1, "PLAY NACHT");
        Menu_DrawGreyButton(2, "COOPERATIVE (UNAVAILABLE)");
        Menu_DrawGreyButton(3, "SETTINGS");
        Menu_DrawGreyButton(4, "CREDITS");
        Menu_DrawGreyButton(5, "EXIT");
        Menu_DrawSubMenu("Exit ZOMBIES?", "Your progress will not be saved.");
        Menu_DrawButton(7, 0, "EXIT GAME", "", Menu_Quit);
        Menu_DrawButton(8, 1, "CANCEL", "", Menu_ExitSubMenu);
    }
}''')
write("menu_main.c", s)

# Hide the old user-map/random list even if an engine path still enters maps.
s = read("menu_stockmaps.c")
s = replace_function(s, "void Menu_StockMaps_Draw (void)", r'''void Menu_StockMaps_Draw (void)
{
    Menu_DrawCustomBackground(true);
    Menu_DrawTitle("ONE MAP", MENU_COLOR_WHITE);
    Menu_DrawMapPanel();
    Menu_DrawMapButton(1, 0, -1, stock_maps[0].category,
        stock_maps[0].bsp_name, Menu_StockMaps_SetMap);
    Menu_DrawButton(-1, 1, "BACK", "Return to main menu.", Menu_StockMaps_SetMainMenu);
}''')
write("menu_stockmaps.c", s)

ids = [i for i in range(1, 62) if i not in (25, 26, 27, 37, 55)]
names = ["M1911","KAR98K","THOMPSON",".357","BAR","BALLISTIC KNIFE","BROWNING",
         "DOUBLE BARREL","FG42","GEWEHR","KAR SCOPE","M1 GARAND","M1A1",
         "FLAMETHROWER","MP40","MG42","PANZER","PPSH","PTRS","RAY GUN",
         "SAWNOFF","STG44","TRENCH","TYPE 100","BIATCH","KILLU",
         "COMPRESSOR","M1000","KOLLIDER","PORTER","WIDDER","FIW",
         "ARMAGEDDON","GIBS","SAMURAI","AFTERBURNER","SPATZ","SNUFF",
         "BORE","IMPELLER","BARRACUDA","ACCELERATOR","GUT","REAPER",
         "HEADCRACKER","LONGINUS","PENETRATOR","WIDOW","KRAUS",
         "MP5K","TESLA","DG3","SPRING","PULVERIZER","RAY GUN MK2","PORTER MK2"]
assert len(names) == len(ids) == 56
ids_c = ", ".join(map(str, ids))
names_c = ", ".join('"'+name+'"' for name in names)

# Hook solo Developer into the SDL native pause C menu. The QC server command
# remains authoritative and refuses public/coop; this UI does not bypass it.
s = read("menu_pause.c")
insert = r'''
// Native mobile dev menu. Only compiled in the isolated developer APK.
static const int xz_native_weapon_ids[56] = {IDS};
static const char *xz_native_weapon_names[56] = {NAMES};
static int xz_native_weapon_page = 0;
static int xz_native_weapon_selected = 0;

static void XzNative_ResetTo(int page)
{
    menu_paus_submenu = page;
    Menu_ResetMenuButtons();
    Menu_SetSound(MENU_SND_ENTER);
}
static void XzNative_Send(int action)
{
    // Native queue -> SSQC xzdev command. A second authority check exists
    // in Command_XzDev on the server.
    if (sv.active && svs.maxclients == 1)
        Cbuf_AddText(va("cmd xzdev %d\n", action));
}
static void XzNative_God(void) { XzNative_Send(1); }
static void XzNative_Ammo(void) { XzNative_Send(2); }
static void XzNative_Refill(void) { XzNative_Send(3); }
static void XzNative_Points(void) { XzNative_Send(4); }
static void XzNative_Open(void) { XzNative_ResetTo(100); }
static void XzNative_Close(void) { XzNative_ResetTo(0); }
static void XzNative_OpenWeapons(void) {
    xz_native_weapon_page = 0;
    XzNative_ResetTo(101);
}
static void XzNative_BackWeapons(void) { XzNative_ResetTo(100); }
static void XzNative_NextPage(void) {
    if ((xz_native_weapon_page+1)*6 < 56) xz_native_weapon_page++;
    Menu_ResetMenuButtons();
}
static void XzNative_PrevPage(void) {
    if (xz_native_weapon_page > 0) xz_native_weapon_page--;
    Menu_ResetMenuButtons();
}
static void XzNative_GiveSelected(void) {
    int i = xz_native_weapon_page*6 + current_menu.cursor;
    if (i >= 0 && i < 56)
        XzNative_Send(100 + xz_native_weapon_ids[i]);
}
static void XzNative_DrawDeveloper(void) {
    Menu_DrawTitle("DEVELOPER TOOLS", MENU_COLOR_WHITE);
    Menu_DrawButton(1, 0, "GOD MODE: TOGGLE", "Solo only.", XzNative_God);
    Menu_DrawButton(2, 1, "INFINITE AMMO: TOGGLE", "Reload animation stays intact.", XzNative_Ammo);
    Menu_DrawButton(3, 2, "REFILL AMMO", "Reload magazines and reserves.", XzNative_Refill);
    Menu_DrawButton(4, 3, "ADD 10,000 POINTS", "Test buys.", XzNative_Points);
    Menu_DrawButton(5, 4, "WEAPON LAB", "Browse 56 original weapons.", XzNative_OpenWeapons);
    Menu_DrawButton(-1, 5, "BACK", "Return to pause.", XzNative_Close);
}
static void XzNative_DrawWeapons(void) {
    int i;
    Menu_DrawTitle("WEAPON LAB", MENU_COLOR_WHITE);
    for (i=0; i<6; ++i) {
        int weapon_idx = xz_native_weapon_page*6 + i;
        if (weapon_idx >= 56) break;
        Menu_DrawButton(i+1, i, (char *)xz_native_weapon_names[weapon_idx],
            "Give original weapon.", XzNative_GiveSelected);
    }
    if (xz_native_weapon_page > 0)
        Menu_DrawButton(-3, 6, "PREVIOUS", "Previous group.", XzNative_PrevPage);
    if ((xz_native_weapon_page+1)*6 < 56)
        Menu_DrawButton(-2, 7, "NEXT", "Next group.", XzNative_NextPage);
    Menu_DrawButton(-1, 8, "BACK", "Developer tools.", XzNative_BackWeapons);
}

'''.replace("IDS",ids_c).replace("NAMES",names_c)
s = replace_once(s, "void Menu_Pause_Draw (void)", insert+"void Menu_Pause_Draw (void)", "native developer hook")
s = replace_function(s, "void Menu_Pause_Draw (void)", r'''void Menu_Pause_Draw (void)
{
    Menu_DrawCustomBackground(true);
    if (menu_paus_submenu == 100) {
        XzNative_DrawDeveloper();
        return;
    }
    if (menu_paus_submenu == 101) {
        XzNative_DrawWeapons();
        return;
    }
    Menu_DrawTitle("PAUSED", MENU_COLOR_WHITE);
    if (menu_paus_submenu == 0) {
        Menu_DrawButton(1, 0, "RESUME", "Return to game.", Menu_Resume);
        Menu_DrawButton(2, 1, "RESTART", "Restart the level.", Menu_Pause_EnterSubMenu);
        Menu_DrawButton(3, 2, "SETTINGS", "Video, sound and touch.", Menu_Configuration);
        Menu_DrawButton(4, 3, "END GAME", "Return to main menu.", Menu_Pause_EnterSubMenu);
        if (sv.active && svs.maxclients == 1)
            Menu_DrawButton(5, 4, "DEVELOPER", "Weapon Lab and test tools.", XzNative_Open);
        else
            Menu_DrawGreyButton(5, "DEVELOPER (SOLO ONLY)");
    } else {
        Menu_DrawGreyButton(1, "RESUME");
        Menu_DrawGreyButton(2, "RESTART");
        Menu_DrawGreyButton(3, "SETTINGS");
        Menu_DrawGreyButton(4, "END GAME");
        if (menu_paus_submenu == 1)
            Menu_DrawSubMenu("Restart the level?", "Progress will be lost.");
        else if (menu_paus_submenu == 3)
            Menu_DrawSubMenu("Return to main menu?", "Progress will be lost.");
        Menu_DrawButton(7, 0, "YES", "", Menu_Pause_Yes);
        Menu_DrawButton(8, 1, "CANCEL", "", Menu_Pause_No);
    }
}''')
write("menu_pause.c", s)
print("Native Vril C menu replaced: single map; branded main; solo dev + 56 weapons.")
