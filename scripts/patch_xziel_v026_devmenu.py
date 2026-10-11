#!/usr/bin/env python3
"""Xziel NZP v0.26: add a *functional* solo-only Developer menu, nothing else.

Input: the September 27 pinned v0.26 engine+QuakeC *after* all original
mobile and official button patches. Only modifies 5 transient upstream files:
- native Vril pause menu (one extra entry and its submenus);
- native Vril back-navigation;
- QuakeC command parser, fields and server update loop.

Preserves original official-button artwork, weapon SWAP, reload+sprint,
HUD, maps, all other menus, package name, and asset layout.
"""
from pathlib import Path
import re, sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: patch_xziel_v026_devmenu.py <build/deps>")
deps = Path(sys.argv[1])
engine = deps / "vril/source/menu"
qc = deps / "quakec/source"

def rw(path):
    if not path.is_file(): raise SystemExit(f"Missing source {path}")
    return path.read_text(encoding="utf-8")

def once(src, old, new, label):
    n = src.count(old)
    if n != 1: raise SystemExit(f"{label}: expected one anchor, got {n}")
    return src.replace(old, new, 1)

def write(path, text):
    path.write_text(text, encoding="utf-8")

# Weapons are indexed by authoritative QuakeC shared_defs.qc, NOT by COD
# stats or arbitrary UI card order. Five IDs are explosives / reserved.
defs = rw(qc / "shared/shared_defs.qc")
weapon_ids = [i for i in range(1, 62) if i not in (25,26,27,37,55)]
catalog = [
    ("COLT M1911", 1), ("KAR98K", 2), ("THOMPSON", 3), (".357 MAGNUM", 4),
    ("BAR", 5), ("BALLISTIC KNIFE", 6), ("BROWNING M1919", 7),
    ("DOUBLE BARREL", 8), ("FG42", 9), ("GEWEHR 43", 10),
    ("SCOPED KAR98K", 11), ("M1 GARAND", 12), ("M1A1 CARBINE", 13),
    ("M2 FLAMETHROWER", 14), ("MP40", 15), ("MG42", 16),
    ("PANZERSCHRECK", 17), ("PPSH-41", 18), ("PTRS-41", 19),
    ("RAY GUN", 20), ("SAWN OFF", 21), ("STG44", 22),
    ("TRENCH GUN", 23), ("TYPE 100", 24),
    ("BIATCH", 28), ("KILLU", 29), ("COMPRESSOR", 30),
    ("M1000", 31), ("KOLLIDER", 32), ("PORTER", 33),
    ("WIDDER", 34), ("FIW", 35), ("ARMAGEDDON", 36),
    ("GIBS", 38), ("SAMURAI", 39), ("AFTERBURNER", 40),
    ("SPATZ", 41), ("SNUFF", 42), ("BORE", 43),
    ("IMPELLER", 44), ("BARRACUDA", 45),
    ("ACCELERATOR", 46), ("GUT", 47), ("REAPER", 48),
    ("HEADCRACKER", 49), ("LONGINUS", 50), ("PENETRATOR", 51),
    ("WIDOW", 52), ("KRAUS", 53), ("MP5K", 54),
    ("TESLA", 56), ("DG3", 57), ("SPRING", 58),
    ("PULVERIZER", 59), ("RAY GUN MK2", 60), ("PORTER MK2", 61)]
assert [w for _,w in catalog] == weapon_ids and len(catalog) == 56
# ID integrity gate: every ID must be declared by the original shared defs.
declared = {int(n) for n in re.findall(r"^#define\s+W_\w+\s+(\d+)\b", defs, re.M)}
assert set(weapon_ids).issubset(declared), set(weapon_ids) - declared

# Gameplay command: server-authoritative; cannot be invoked in network Co-op.
path = qc / "server/defs/custom.qc"
s = rw(path)
s += "\n.float xziel_dev_infinite_reserve; // v0.26 solo developer toggle.\n"
write(path, s)

path = qc / "server/utilities/command_parser.qc"
s = rw(path)
impl = r'''
// v0.26 Developer actions: a real QuakeC command, not a UI-only toggle.
// When called from native Vril's PAUSE, the game is resumed first so that
// localhost client commands are actually pumped by the server. Do not
// forward or execute in online / co-op (including single player in 4P lobby).
float(string params) Command_XzielDev =
{
    if (self.classname != "player" ||
        player_count != 1 || cvar("maxclients") > 1) {
        sprint(self, 1, "XZIEL DEV: unavailable online.\n");
        return COMMAND_FAILURE;
    }
    tokenize(params);
    float action = stof(argv(0));
    if (action == 1) {
        if (self.flags & FL_GODMODE) {
            self.flags = self.flags - FL_GODMODE;
            centerprint(self, "DEV: GOD MODE OFF");
        } else {
            self.flags = self.flags | FL_GODMODE;
            centerprint(self, "DEV: GOD MODE ON");
        }
        return COMMAND_SUCCESS;
    }
    if (action == 2) {
        self.xziel_dev_infinite_reserve = !self.xziel_dev_infinite_reserve;
        if (self.xziel_dev_infinite_reserve)
            centerprint(self, "DEV: INFINITE RESERVE ON");
        else
            centerprint(self, "DEV: INFINITE RESERVE OFF");
        return COMMAND_SUCCESS;
    }
    if (action == 3) {
        for (float i = 0; i < MAX_PLAYER_WEAPONS; i++) {
            float wid = self.weapons[i].weapon_id;
            if (!wid) continue;
            self.weapons[i].weapon_magazine = getWeaponMag(wid);
            if (IsDualWeapon(wid))
                self.weapons[i].weapon_magazine_left = getWeaponMag(wid);
            self.weapons[i].weapon_reserve = getWeaponAmmo(wid);
        }
        centerprint(self, "DEV: ALL AMMO REFILLED");
        return COMMAND_SUCCESS;
    }
    if (action == 4) {
        Player_ChangeScore(self, 10000, false);
        centerprint(self, "DEV: +10000 POINTS");
        return COMMAND_SUCCESS;
    }
    if (action >= 101 && action <= 161) {
        float weapon_id = action - 100;
        if (weapon_id == W_BOWIE || weapon_id == W_GRENADE ||
            weapon_id == W_BETTY || weapon_id == W_RESERVED ||
            weapon_id == W_RESERVED2)
            return COMMAND_FAILURE;
        Weapon_GiveWeapon(weapon_id, 0, 0, 0);
        centerprint(self, "DEV: WEAPON EQUIPPED");
        return COMMAND_SUCCESS;
    }
    centerprint(self, "DEV: UNKNOWN ACTION");
    return COMMAND_FAILURE;
}

'''
s = once(s, "//\n// Server command table\n", impl+"//\n// Server command table\n", "QC command body")
s = once(s, '    {"addmoney", Command_addmoney,',
    '    {"xzdev", Command_XzielDev, true, "Usage: xzdev <action>. Solo developer menu.\\n"},\n    {"addmoney", Command_addmoney,',
    "QC table registration")
write(path, s)

# Native Vril does not whitelist "xzdev" string commands in sv_user.c.
# The existing v0.26 input engine DOES send 'impulse N' as a usercmd byte.
# Intercept reserved developer impulses BEFORE the stock weapon-core switch.
# This is the actual touch->client usercmd->server QuakeC action authority.
path = qc / "server/weapons/weapon_core.qc"
s = rw(path)
hook = r"""
float(string params) Command_XzielDev; // server authoritative action handler
void () Impulse_Functions =
{
    if (!self.impulse) return;

    if (self.impulse >= 181 && self.impulse <= 245) {
        float dev_impulse = self.impulse;
        self.impulse = 0;
        float action;
        if (dev_impulse >= 242)
            action = dev_impulse - 241; // 1=god, 2=ammo, 3=refill, 4=points
        else
            action = dev_impulse - 80;  // 101..161: weapon ID 1..61
        Command_XzielDev(ftos(action));
        return;
    }
"""
# Keep all stock player impulse cases untouched and reachable afterward.
s = once(s, "void () Impulse_Functions =\n{\n\tif (!self.impulse)\n\t\treturn;\n",
         hook, "wire touch input to true server-side gameplay impulse")
write(path, s)

# Infinite reserve: changed only when dev toggle enabled and only *after*
# resuming gameplay; keep the original reload magazine callbacks intact.
path = qc / "server/main.qc"
s = rw(path)
s = once(s, "\tframecount = framecount + 1;",
'''\tframecount = framecount + 1;
    entity xziel_dev_player = find(world, classname, "player");
    while (xziel_dev_player != world) {
        if (xziel_dev_player.xziel_dev_infinite_reserve &&
            player_count == 1 && cvar("maxclients") <= 1) {
            for (float i = 0; i < MAX_PLAYER_WEAPONS; i++) {
                float wid = xziel_dev_player.weapons[i].weapon_id;
                if (wid && getWeaponAmmo(wid) > 0)
                    xziel_dev_player.weapons[i].weapon_reserve = getWeaponAmmo(wid);
            }
        }
        xziel_dev_player = find(xziel_dev_player, classname, "player");
    }''',
"QC infinite-reserve frame guard")
# Weapon Lab must have weapon viewmodels precached at world spawn; this
# matches existing mystery-box/gun-game pre-cache sequence.
s = once(s, "\tprecache_extra (W_BIATCH);",
'''\tprecache_extra (W_BIATCH);
    // v0.26 Developer Weapon Lab, 56 IDs (no melee/grenade/reserved).
    if (cvar("maxclients") <= 1) {
        for (float wid = 1; wid <= 61; wid++) {
            if (wid == W_BOWIE || wid == W_GRENADE || wid == W_BETTY ||
                wid == W_RESERVED || wid == W_RESERVED2) continue;
            string viewmodel = GetWeaponModel(wid, 0);
            string groundmodel = GetWeaponModel(wid, 1);
            if (viewmodel != "") precache_model(viewmodel);
            if (groundmodel != "") precache_model(groundmodel);
            precache_extra(wid);
        }
    }''', "weapon lab model precache")
write(path, s)

# The original v0.26 Android menu has RESUME, RESTART, OPTIONS, SAVE & EXIT,
# EXIT TO MENU. Insert DEVELOPER at the end of that existing Android section.
path = engine / "menu_pause.c"
s = rw(path)
data = ', '.join(str(id) for _, id in catalog)
labels = ', '.join('"'+name+'"' for name, _ in catalog)
ui = r'''
// XZIEL v0.26: ONLY added Developer pause submenu. Never touch mobile HUD.
static const int xziel_dev_weapon_ids[56] = {IDS};
static const char *xziel_dev_weapon_names[56] = {NAMES};
static int xziel_dev_weapon_page;

static void XzielDev_Menu(int target)
{
    menu_paus_submenu = target;
    Menu_ResetMenuButtons();
    Menu_SetSound(MENU_SND_ENTER);
}
static void XzielDev_Send(int action)
{
    if (!sv.active || svs.maxclients != 1) return;
    // CRITICAL: Xziel's Android Pause_Set sets sv.paused. Old Dev menus
    // submitted server commands while the game was frozen, so the server
    // never processed the action. Resume first; send on next frame.
    Menu_Resume();
    // Vril's server command whitelist silently rejects custom stringcmd
    // commands (cmd xzdev). Use the *already working* engine 'impulse'
    // pipeline instead, just like CROUCH / PRONE / SLIDE in v0.26.
    // 181..241 => 56 weapon IDs, 242..245 => God/Ammo/Refill/Points.
    int impulse = action >= 101 ? action + 80 : action + 241;
    Cbuf_AddText(va("impulse %d\n", impulse));
    Con_Printf("XZIEL DEV: sent gameplay impulse %d for action %d\n",
               impulse, action);
}
static void XzielDev_God(void) { XzielDev_Send(1); }
static void XzielDev_Ammo(void) { XzielDev_Send(2); }
static void XzielDev_Refill(void) { XzielDev_Send(3); }
static void XzielDev_Points(void) { XzielDev_Send(4); }
static void XzielDev_Open(void) { XzielDev_Menu(100); }
static void XzielDev_Back(void) { XzielDev_Menu(0); }
static void XzielDev_Weapons(void) { xziel_dev_weapon_page = 0; XzielDev_Menu(101); }
static void XzielDev_BackWeapons(void) { XzielDev_Menu(100); }
static void XzielDev_Next(void) {
    if ((xziel_dev_weapon_page+1)*5 < 56) ++xziel_dev_weapon_page;
    Menu_ResetMenuButtons();
}
static void XzielDev_Previous(void) {
    if (xziel_dev_weapon_page > 0) --xziel_dev_weapon_page;
    Menu_ResetMenuButtons();
}
static void XzielDev_Give(void)
{
    int index = xziel_dev_weapon_page*5 + current_menu.cursor;
    if (index >= 0 && index < 56)
        XzielDev_Send(100 + xziel_dev_weapon_ids[index]);
}
static void XzielDev_Draw(void)
{
    Menu_DrawCustomBackground(true);
    if (menu_paus_submenu == 100) {
        Menu_DrawTitle("XZIEL DEVELOPER", MENU_COLOR_WHITE);
        Menu_DrawButton(1, 0, "GOD MODE: TOGGLE", "Applied after resume.", XzielDev_God);
        Menu_DrawButton(2, 1, "INFINITE RESERVE: TOGGLE", "Reloads remain authentic.", XzielDev_Ammo);
        Menu_DrawButton(3, 2, "REFILL ALL AMMO", "Refill equipped weapons.", XzielDev_Refill);
        Menu_DrawButton(4, 3, "+10,000 POINTS", "Applies to your solo player.", XzielDev_Points);
        Menu_DrawButton(5, 4, "WEAPON LAB: 56", "Original NZ:P weapons and variants.", XzielDev_Weapons);
        Menu_DrawButton(-1, 5, "BACK", "Return to Pause.", XzielDev_Back);
        return;
    }
    Menu_DrawTitle("XZIEL WEAPON LAB", MENU_COLOR_WHITE);
    int i;
    for (i=0; i<5; ++i) {
        int ix = xziel_dev_weapon_page*5 + i;
        if (ix >= 56) break;
        Menu_DrawButton(i+1, i, (char*)xziel_dev_weapon_names[ix],
                        "Equip and return to game.", XzielDev_Give);
    }
    // Keep *contiguous* indices for touch hitboxes, including last page.
    int nav=i;
    if (xziel_dev_weapon_page > 0)
        Menu_DrawButton(-3, nav++, "PREV PAGE", "", XzielDev_Previous);
    if ((xziel_dev_weapon_page+1)*5 < 56)
        Menu_DrawButton(-2, nav++, "NEXT PAGE", "", XzielDev_Next);
    Menu_DrawButton(-1, nav, "BACK", "Developer menu.", XzielDev_BackWeapons);
}
qboolean XzielDev_ConsumeBack(void)
{
    if (menu_paus_submenu == 101) {
        XzielDev_BackWeapons();
        return true;
    }
    if (menu_paus_submenu == 100) {
        XzielDev_Back();
        return true;
    }
    return false;
}
'''.replace("IDS", data).replace("NAMES", labels)
s = once(s, "void Menu_Pause_Draw (void)\n", ui+"\nvoid Menu_Pause_Draw (void)\n", "native pause hook")
s = once(s, "void Menu_Pause_Draw (void)\n{", 
'''void Menu_Pause_Draw (void)
{
    if (menu_paus_submenu == 100 || menu_paus_submenu == 101) {
        XzielDev_Draw();
        return;
    }''', "native submenu draw")
s = once(s,
    'Menu_DrawButton (5, 4, "EXIT TO MENU",\n\t\t\t"Return to Main Menu without saving.", Menu_Pause_EnterSubMenu);',
    'Menu_DrawButton (5, 4, "EXIT TO MENU",\n\t\t\t"Return to Main Menu without saving.", Menu_Pause_EnterSubMenu);\n'
    '        if (sv.active && svs.maxclients == 1)\n'
    '            Menu_DrawButton(6, 5, "DEVELOPER", "Solo testing tools.", XzielDev_Open);',
    "Android-specific pause button")
write(path, s)

path = engine / "menu_sys.c"
s = rw(path)
s = once(s, "void Menu_KeyInput (int key)",
    "qboolean XzielDev_ConsumeBack(void);\n\nvoid Menu_KeyInput (int key)", "native back declaration")
s = once(s,
    "if (m_state == m_pause && menu_paus_submenu == 0)",
    "if (m_state == m_pause && XzielDev_ConsumeBack()) return;\n"
    "\t\tif (m_state == m_pause && menu_paus_submenu == 0)",
    "Android back interception")
write(path, s)
print("PASS: original Xziel NZP v0.26 intact; real server xzdev command + resume-before-dispatch; native solo Developer menu.")
