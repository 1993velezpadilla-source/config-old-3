#!/usr/bin/env python3
"""Optional single-map menus + authoritative solo developer tools for NZ:P/Vril."""
from pathlib import Path
import re
import sys

if len(sys.argv) != 4 or sys.argv[3] not in ("0", "1"):
    raise SystemExit("usage: patch_vril_one_map_devmenu.py <quakec-dir> <map-id> <0|1>")
src = Path(sys.argv[1]) / "source"
target = sys.argv[2]
developer = sys.argv[3] == "1"
if not re.fullmatch(r"[A-Za-z0-9_-]+", target):
    raise SystemExit("Unsafe map id")

def get(name):
    return (src / name).read_text(encoding="utf-8")

def put(name, s):
    (src / name).write_text(s, encoding="utf-8")

def once(s, old, new, label):
    if s.count(old) != 1:
        raise SystemExit("Upstream changed, expected exactly one " + label)
    return s.replace(old, new, 1)

def fun(s, signature, new):
    start = s.find(signature)
    if start < 0:
        raise SystemExit("Missing function: " + signature)
    left = s.find("{", start)
    depth, right = 0, -1
    for i in range(left, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                right = i + 1
                break
    if right < 0:
        raise SystemExit("Unterminated function: " + signature)
    if right < len(s) and s[right] == ";":
        right += 1
    return s[:start] + new + s[right:]

p = "menu/menu_main.qc"
s = get(p)
s = once(s, 'string menu_main_buttons[6] = {"mm_start", "mm_coop", "mm_options", "mm_bios", "mm_credits", "mm_quit"};',
         'string menu_main_buttons[5] = {"mm_start", "mm_coop", "mm_options", "mm_credits", "mm_quit"};\n'
         'void(string bsp_name) Menu_Maps_LoadMap;', "main menu button registry")
s = fun(s, "void() Menu_Main =", r'''void() Menu_Main =
{
    Menu_DrawBackground();
    Menu_DrawTitle("ZOMBIES");
    Menu_DrawBuildDate();
    if (Menu_Button(1, "mm_start", "PLAY", "The single-map experience.")) {
        Menu_StartSolo();
        Menu_Maps_LoadMap("MAP_NAME");
    }
    Menu_Button(2, "mm_coop", "COOPERATIVE", "Four-player coop.") ? current_menu = MENU_COOP : 0;
    Menu_DrawDivider(3);
    Menu_Button(3.25, "mm_options", "SETTINGS", "Video, audio and touch.") ? current_menu = MENU_OPTIONS : 0;
    Menu_Button(4.25, "mm_credits", "CREDITS", "Upstream creators and acknowledgements.") ? current_menu = MENU_CREDITS : 0;
    if (running_platform != PLATFORM_WEB)
        Menu_Button(5.5, "mm_quit", "EXIT", "Exit game.") ? localcmd("quit\n") : 0;
    sui_pop_frame();
};'''.replace("MAP_NAME", target))
put(p, s)

p = "menu/menu_maps.qc"
s = get(p)
s = fun(s, "void() Menu_Maps =", r'''void() Menu_Maps =
{
    Menu_DrawBackground();
    Menu_DrawTitle("SELECT MAP");
    for (int i = 0; i < 13; i++) menu_maps_buttons[i] = "";
    menu_maps_buttons[0] = "map_only";
    menu_maps_buttons[1] = "map_back";
    Menu_Button(1, "map_only", "PLAY", "Launch the one available map.")
        ? Menu_Maps_LoadMap("MAP_NAME") : 0;
    Menu_Button(-1, "map_back", "BACK", "Return to menu.")
        ? current_menu = ((menu_map_mode == MAP_SOLOSTOCK || menu_map_mode == MAP_SOLOUSER)
            ? MENU_MAIN : MENU_COOPCREATE) : 0;
    sui_pop_frame();
};'''.replace("MAP_NAME", target))
put(p, s)

if not developer:
    print("Single-map layout installed. Dev tools OFF.")
    raise SystemExit(0)

p = "server/defs/custom.qc"
put(p, get(p) + "\n.float xzdev_infinite_reserve; // Solo developer test state.\n")

p = "server/utilities/command_parser.qc"
s = get(p)
command = r'''
// Built only into developer APKs; cannot be used in coop/public sessions.
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
s = once(s, "//\n// Server command table\n", command + "//\n// Server command table\n", "server command table")
s = once(s, '    {"addmoney", Command_addmoney,', '    {"xzdev", Command_XzDev, true, "Solo developer action."},\n    {"addmoney", Command_addmoney,', "xzdev command registration")
put(p, s)

# Refill reserves once per frame only when the local player has opted in.
# Magazine counts are untouched to keep reloads (including MP40) testable.
p = "server/main.qc"
s = get(p)
s = once(s, "precache_extra (W_BIATCH);", """precache_extra (W_BIATCH);

    // Precache weapon models + sounds even when they are normally found only
    // on another map. Only done in this opt-in developer game build.
    for (float wid = 1; wid <= 61; wid++) {
        if (wid == 25 || wid == 26 || wid == 27 || wid == 37 || wid == 55)
            continue;
        string viewmdl = GetWeaponModel(wid, 0);
        string worldmdl = GetWeaponModel(wid, 1);
        if (viewmdl != "") precache_model(viewmdl);
        if (worldmdl != "") precache_model(worldmdl);
        precache_extra(wid);
    }""", "all-map developer arsenal precache")
s = once(s, "framecount = framecount + 1;", """framecount = framecount + 1;
    entity p_dev = find(world, classname, "player");
    while (p_dev != world) {
        if (p_dev.xzdev_infinite_reserve) {
            for (float i = 0; i < MAX_PLAYER_WEAPONS; i++) {
                float wid = p_dev.weapons[i].weapon_id;
                if (wid && getWeaponAmmo(wid) > 0)
                    p_dev.weapons[i].weapon_reserve = getWeaponAmmo(wid);
                // M2 / F1W are fuel-magazine weapons with no reserve pool.
                if (wid == W_M2 || wid == W_FIW)
                    p_dev.weapons[i].weapon_magazine = getWeaponMag(wid);
            }
        }
        p_dev = find(p_dev, classname, "player");
    }""", "developer ammo replenishment")
put(p, s)

# Inventory-ready original weapon IDs; excludes standalone grenades/knife and
# reserved slots. Keeps weapon assets for all maps in the archive.
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
if len(ids) != len(names):
    raise SystemExit("Weapon index/label table mismatch")

p = "menu/menu_paus.qc"
s = get(p)
s = once(s, "string menu_paus_buttons[4];",
         "string menu_paus_buttons[9];\nfloat xzdev_weapon_page;", "pause registry")
s = fun(s, "string(string prev_id) Menu_Pause_GetNextButton =", r'''string(string prev_id) Menu_Pause_GetNextButton =
{
    if (prev_id == "") return menu_paus_buttons[0];
    for (float i = 0; i < menu_paus_buttons.length; i++)
        if (menu_paus_buttons[i] == prev_id) {
            for (float j = i + 1; j < menu_paus_buttons.length; j++)
                if (menu_paus_buttons[j] != "") return menu_paus_buttons[j];
            return menu_paus_buttons[0];
        }
    return menu_paus_buttons[0];
};''')
s = fun(s, "string(string next_id) Menu_Pause_GetPreviousButton =", r'''string(string next_id) Menu_Pause_GetPreviousButton =
{
    string last = "";
    for (float i = 0; i < menu_paus_buttons.length; i++)
        if (menu_paus_buttons[i] != "") last = menu_paus_buttons[i];
    if (next_id == "") return last;
    for (float j = 0; j < menu_paus_buttons.length; j++)
        if (menu_paus_buttons[j] == next_id) {
            for (float k = j - 1; k >= 0; k--)
                if (menu_paus_buttons[k] != "") return menu_paus_buttons[k];
            return last;
        }
    return last;
};''')

panel = '''
float xzdev_weapon_ids[] = {IDS};
string xzdev_weapon_names[] = {NAMES};

void(float action) XzDev_Action =
{
    localcmd(sprintf("cmd xzdev %d\\n", action));
};

void() XzDev_PausePanel =
{
    Menu_DrawBackground();
    for (float i = 0; i < menu_paus_buttons.length; i++) menu_paus_buttons[i] = "";
    if (menu_paus_submenu == 3) {
        Menu_DrawTitle("DEVELOPER");
        menu_paus_buttons[0] = "xd_god";
        menu_paus_buttons[1] = "xd_ammo";
        menu_paus_buttons[2] = "xd_refill";
        menu_paus_buttons[3] = "xd_money";
        menu_paus_buttons[4] = "xd_weapons";
        menu_paus_buttons[5] = "xd_back";
        Menu_Button(1, "xd_god", "GOD MODE / TOGGLE", "Solo invulnerability.") ? XzDev_Action(1) : 0;
        Menu_Button(2, "xd_ammo", "INFINITE AMMO / TOGGLE", "Infinite reserve; actual reloads.") ? XzDev_Action(2) : 0;
        Menu_Button(3, "xd_refill", "REFILL ALL AMMO", "All carried weapon magazines.") ? XzDev_Action(3) : 0;
        Menu_Button(4, "xd_money", "+10000 POINTS", "Test buys and perks.") ? XzDev_Action(4) : 0;
        if (Menu_Button(5, "xd_weapons", "WEAPON LAB", "Access original weapon catalogue.")) {
            xzdev_weapon_page = 0;
            menu_paus_submenu = 4;
        }
        Menu_Button(-1, "xd_back", "BACK TO PAUSE", "Return.") ? menu_paus_submenu = 0 : 0;
    } else {
        Menu_DrawTitle("WEAPON LAB");
        for (float i = 0; i < 6; i++) {
            float idx = xzdev_weapon_page * 6 + i;
            if (idx >= xzdev_weapon_ids.length) break;
            string button_id = sprintf("xd_w%d", idx);
            menu_paus_buttons[i] = button_id;
            Menu_Button(i + 1, button_id, xzdev_weapon_names[idx], "Give this original weapon.")
                ? XzDev_Action(100 + xzdev_weapon_ids[idx]) : 0;
        }
        menu_paus_buttons[6] = "xd_prev";
        menu_paus_buttons[7] = "xd_next";
        menu_paus_buttons[8] = "xd_return";
        if (xzdev_weapon_page > 0)
            Menu_Button(-3, "xd_prev", "PREVIOUS", "Previous page.") ? xzdev_weapon_page-- : 0;
        else Menu_GreyButton(-3, "PREVIOUS");
        if ((xzdev_weapon_page + 1) * 6 < xzdev_weapon_ids.length)
            Menu_Button(-2, "xd_next", "NEXT", "Next page.") ? xzdev_weapon_page++ : 0;
        else Menu_GreyButton(-2, "NEXT");
        Menu_Button(-1, "xd_return", "BACK TO DEVELOPER", "Return.")
            ? menu_paus_submenu = 3 : 0;
    }
    sui_pop_frame();
};

'''.replace("IDS", ", ".join(str(i) for i in ids)).replace("NAMES", ", ".join('"' + n + '"' for n in names))
s = once(s, "void() Menu_Pause =\n{",
         panel + "void() Menu_Pause =\n{\n"
         "    if (menu_paus_submenu == 3 || menu_paus_submenu == 4) {\n"
         "        XzDev_PausePanel();\n        return;\n    }\n", "pause developer panel")
s = once(s,
  '        Menu_Button(4, "pm_quit", "END GAME", "Return to Main Menu.") ? Menu_Pause_EnterSubMenu(2) : 0;',
  '        Menu_Button(4, "pm_quit", "END GAME", "Return to Main Menu.") ? Menu_Pause_EnterSubMenu(2) : 0;\n'
  '        if (player_count == 1) Menu_Button(5, "pm_dev", "DEVELOPER", "Solo testing tools.") ? Menu_Pause_EnterSubMenu(3) : 0;\n'
  '        else Menu_GreyButton(5, "DEVELOPER (SOLO ONLY)");',
  "pause developer entry")
s = once(s, '        menu_paus_buttons[3] = "pm_quit";',
         '        menu_paus_buttons[3] = "pm_quit";\n'
         '        menu_paus_buttons[4] = "pm_dev";\n'
         '        for (int i = 5; i < menu_paus_buttons.length; i++) menu_paus_buttons[i] = "";',
         "pause main navigation")
s = once(s, '        menu_paus_buttons[3] = "";',
         '        menu_paus_buttons[3] = "";\n'
         '        for (int i = 4; i < menu_paus_buttons.length; i++) menu_paus_buttons[i] = "";',
         "pause confirmation navigation")
put(p, s)
print("Developer controls + %d inventory-ready original weapons patched" % len(ids))
