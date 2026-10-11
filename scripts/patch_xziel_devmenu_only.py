#!/usr/bin/env python3
"""Add ONLY a Developer pause submenu to baseline Xziel NZP Native.

Native SDL/Vril pause menu is C, and the gameplay server is QuakeC.
This overlay intentionally does NOT touch main menu, maps, HUD, touch assets,
app ID, icon, weapons, movement, renderer, or user settings.
"""
from pathlib import Path
import re
import sys

if len(sys.argv) != 3 or sys.argv[2] != "1":
    raise SystemExit("usage: patch_xziel_devmenu_only.py <build/deps-root> 1")
deps = Path(sys.argv[1])
native_menu = deps / "vril" / "source" / "menu"
qc = deps / "quakec" / "source"

def exact(src, old, new, label):
    found = src.count(old)
    if found != 1:
        raise SystemExit(f"XZIEL dev menu source drift: {label}: {found} anchors")
    return src.replace(old, new, 1)

def read(path):
    return path.read_text(encoding="utf-8")

def save(path, content):
    path.write_text(content, encoding="utf-8")

# Server-authoritative commands. This code is not present in release builds.
path = qc / "server/defs/custom.qc"
s = read(path)
if "xzdev_infinite_reserve" in s:
    raise SystemExit("Refusing duplicate Xziel developer patch")
save(path, s + "\n.float xzdev_infinite_reserve; // Xziel solo developer testing.\n")

path = qc / "server/utilities/command_parser.qc"
s = read(path)
command = r'''
// Xziel developer actions: opt-in build, solo/private only.
float(string params) Command_XzDev =
{
    if (player_count != 1 || cvar("sv_public") != 0)
        return COMMAND_FAILURE;
    float action = stof(params);
    if (action == 1) {
        if (self.flags & FL_GODMODE) self.flags = self.flags - FL_GODMODE;
        else self.flags = self.flags | FL_GODMODE;
        return COMMAND_SUCCESS;
    }
    if (action == 2) {
        self.xzdev_infinite_reserve = !self.xzdev_infinite_reserve;
        return COMMAND_SUCCESS;
    }
    if (action == 3) {
        for (float i = 0; i < MAX_PLAYER_WEAPONS; i++) {
            float id = self.weapons[i].weapon_id;
            if (!id) continue;
            self.weapons[i].weapon_magazine = getWeaponMag(id);
            if (IsDualWeapon(id)) self.weapons[i].weapon_magazine_left = getWeaponMag(id);
            self.weapons[i].weapon_reserve = getWeaponAmmo(id);
        }
        return COMMAND_SUCCESS;
    }
    if (action == 4) {
        Player_ChangeScore(self, 10000, false);
        return COMMAND_SUCCESS;
    }
    if (action >= 101 && action <= 161) {
        float id = action - 100;
        if (id == 25 || id == 26 || id == 27 || id == 37 || id == 55)
            return COMMAND_FAILURE;
        Weapon_GiveWeapon(id, 0, 0, 0);
        return COMMAND_SUCCESS;
    }
    return COMMAND_FAILURE;
}

'''
s = exact(s, "//\n// Server command table\n",
          command + "//\n// Server command table\n", "QC server command table")
s = exact(s, '    {"addmoney", Command_addmoney,',
          '    {"xzdev", Command_XzDev, true, "Solo developer action."},\n'
          '    {"addmoney", Command_addmoney,', "QC command registration")
save(path, s)

# Allow the Weapon Lab to equip other-map guns without asking for other maps.
# Keep reloads authentic; the infinity toggle refills reserve, not magazine.
path = qc / "server/main.qc"
s = read(path)
s = exact(s, "precache_extra (W_BIATCH);",
    """precache_extra (W_BIATCH);
    // Xziel Developer Weapon Lab: load models/audio for selectable guns.
    for (float wid = 1; wid <= 61; wid++) {
        if (wid == 25 || wid == 26 || wid == 27 || wid == 37 || wid == 55)
            continue;
        string v = GetWeaponModel(wid, 0);
        string g = GetWeaponModel(wid, 1);
        if (v != "") precache_model(v);
        if (g != "") precache_model(g);
        precache_extra(wid);
    }""", "weapon cache")
s = exact(s, "framecount = framecount + 1;",
    """framecount = framecount + 1;
    entity xz_dev_p = find(world, classname, "player");
    while (xz_dev_p != world) {
        if (xz_dev_p.xzdev_infinite_reserve) {
            for (float xz_i = 0; xz_i < MAX_PLAYER_WEAPONS; xz_i++) {
                float wid = xz_dev_p.weapons[xz_i].weapon_id;
                if (wid && getWeaponAmmo(wid) > 0)
                    xz_dev_p.weapons[xz_i].weapon_reserve = getWeaponAmmo(wid);
                if (wid == W_M2 || wid == W_FIW)
                    xz_dev_p.weapons[xz_i].weapon_magazine = getWeaponMag(wid);
            }
        }
        xz_dev_p = find(xz_dev_p, classname, "player");
    }""", "server update")
save(path, s)

# Native C menu, NOT QuakeC menu/menu_paus.qc.
weapon_ids = [i for i in range(1, 62) if i not in (25, 26, 27, 37, 55)]
weapon_names = ["M1911", "KAR98K", "THOMPSON", ".357", "BAR", "BALLISTIC KNIFE",
                "BROWNING", "DOUBLE BARREL", "FG42", "GEWEHR", "KAR SCOPE",
                "M1 GARAND", "M1A1", "FLAMETHROWER", "MP40", "MG42", "PANZER",
                "PPSH", "PTRS", "RAY GUN", "SAWNOFF", "STG44", "TRENCH",
                "TYPE 100", "BIATCH", "KILLU", "COMPRESSOR", "M1000",
                "KOLLIDER", "PORTER", "WIDDER", "FIW", "ARMAGEDDON", "GIBS",
                "SAMURAI", "AFTERBURNER", "SPATZ", "SNUFF", "BORE",
                "IMPELLER", "BARRACUDA", "ACCELERATOR", "GUT", "REAPER",
                "HEADCRACKER", "LONGINUS", "PENETRATOR", "WIDOW", "KRAUS",
                "MP5K", "TESLA", "DG3", "SPRING", "PULVERIZER",
                "RAY GUN MK2", "PORTER MK2"]
if len(weapon_names) != 56 or len(weapon_ids) != 56:
    raise SystemExit("Invalid Weapon Lab catalog")

path = native_menu / "menu_pause.c"
s = read(path)
panel = r'''
// XZIEL DEV MENU — isolated, opt-in. Native pause UI only.
static const int xz_dev_ids[56] = {IDS};
static const char* xz_dev_names[56] = {NAMES};
static int xz_dev_page;

static void XzDev_Switch(int page)
{
    menu_paus_submenu = page;
    Menu_ResetMenuButtons();
    Menu_SetSound(MENU_SND_ENTER);
}
static void XzDev_Command(int action)
{
    // Server Command_XzDev independently rejects coop/public calls.
    if (sv.active && svs.maxclients == 1)
        Cbuf_AddText(va("cmd xzdev %d\n", action));
}
static void XzDev_God(void) { XzDev_Command(1); }
static void XzDev_Infinite(void) { XzDev_Command(2); }
static void XzDev_Refill(void) { XzDev_Command(3); }
static void XzDev_Points(void) { XzDev_Command(4); }
static void XzDev_Open(void) { XzDev_Switch(100); }
static void XzDev_ReturnPause(void) { XzDev_Switch(0); }
static void XzDev_OpenWeapons(void) { xz_dev_page = 0; XzDev_Switch(101); }
static void XzDev_ReturnTools(void) { XzDev_Switch(100); }
static void XzDev_Next(void) {
    if ((xz_dev_page+1)*6 < 56) xz_dev_page++;
    Menu_ResetMenuButtons();
}
static void XzDev_Prev(void) {
    if (xz_dev_page > 0) xz_dev_page--;
    Menu_ResetMenuButtons();
}
static void XzDev_Give(void) {
    int index = xz_dev_page*6 + current_menu.cursor;
    if (index >= 0 && index < 56)
        XzDev_Command(100 + xz_dev_ids[index]);
}
static void XzDev_Draw(void)
{
    int i;
    Menu_DrawCustomBackground(true);
    if (menu_paus_submenu == 100) {
        Menu_DrawTitle("XZIEL DEVELOPER", MENU_COLOR_WHITE);
        Menu_DrawButton(1, 0, "GOD MODE (TOGGLE)", "Solo test.", XzDev_God);
        Menu_DrawButton(2, 1, "INFINITE AMMO (TOGGLE)", "Real reload animations.", XzDev_Infinite);
        Menu_DrawButton(3, 2, "REFILL ALL AMMO", "Magazines and reserves.", XzDev_Refill);
        Menu_DrawButton(4, 3, "+10,000 POINTS", "Test map purchases.", XzDev_Points);
        Menu_DrawButton(5, 4, "WEAPON LAB", "56 original weapons / variants.", XzDev_OpenWeapons);
        Menu_DrawButton(-1, 5, "BACK TO PAUSE", "", XzDev_ReturnPause);
        return;
    }
    Menu_DrawTitle("XZIEL WEAPON LAB", MENU_COLOR_WHITE);
    for (i = 0; i < 6; ++i) {
        int index = xz_dev_page*6 + i;
        if (index >= 56) break;
        Menu_DrawButton(i+1, i, (char*)xz_dev_names[index],
                        "Give weapon.", XzDev_Give);
    }
    // Dense continuous indices, especially on the last two-weapon page.
    int nav = i;
    if (xz_dev_page > 0)
        Menu_DrawButton(-3, nav++, "PREVIOUS", "", XzDev_Prev);
    if ((xz_dev_page+1)*6 < 56)
        Menu_DrawButton(-2, nav++, "NEXT", "", XzDev_Next);
    Menu_DrawButton(-1, nav, "BACK", "Developer tools.", XzDev_ReturnTools);
}
// Returning true means we consumed native Android Back or Escape.
qboolean XzDev_PauseHandleBack(void)
{
    if (menu_paus_submenu == 101) {
        XzDev_ReturnTools();
        return true;
    }
    if (menu_paus_submenu == 100) {
        XzDev_ReturnPause();
        return true;
    }
    return false;
}

'''.replace("IDS", ", ".join(map(str, weapon_ids))).replace(
    "NAMES", ", ".join('"'+x+'"' for x in weapon_names))
s = exact(s, "void Menu_Pause_Draw (void)", panel+"void Menu_Pause_Draw (void)",
          "C pause menu hook")
s = exact(s, """void Menu_Pause_Draw (void)
{
""", """void Menu_Pause_Draw (void)
{
    if (menu_paus_submenu == 100 || menu_paus_submenu == 101) {
        XzDev_Draw();
        return;
    }
""", "C pause draw guard")
s = exact(s,
    'Menu_DrawButton (4, 3, "END GAME", "Return to Main Menu.", Menu_Pause_EnterSubMenu);',
    'Menu_DrawButton (4, 3, "END GAME", "Return to Main Menu.", Menu_Pause_EnterSubMenu);\n'
    '        if (sv.active && svs.maxclients == 1)\n'
    '            Menu_DrawButton(5, 4, "DEVELOPER", "Solo testing tools.", XzDev_Open);',
    "C pause developer button")
save(path, s)

# Android hardware Back / Escape unwinds ONLY developer submenus.
path = native_menu / "menu_sys.c"
s = read(path)
s = exact(s, "void Menu_KeyInput (int key)",
          "qboolean XzDev_PauseHandleBack(void);\n\nvoid Menu_KeyInput (int key)",
          "C native back prototype")
s = exact(s, "if (m_state == m_pause && menu_paus_submenu == 0)",
          "if (m_state == m_pause && XzDev_PauseHandleBack()) return;\n"
          "        if (m_state == m_pause && menu_paus_submenu == 0)",
          "C native back route")
save(path, s)
print("PASS: Xziel original Android menus/HUD/maps preserved; only pause developer + server commands patched")
