#!/usr/bin/env python3
"""Safe, opt-in 2-map NZ:P v0.26 Android package and touch-friendly quick menu.

Run ONLY after scripts/prepare_android.sh builds transient build/deps/vril and
nzp-data.zip and after Sanctum HQ assets are overlaid into that zip.
Nothing in the original Vril source repository or previous APK is deleted.
"""
from pathlib import Path
from zipfile import ZipFile
import hashlib
import os
import re
import shutil
import sys
import tempfile

MAP_NAMES = ("sanctum_harness", "xziel_proto")
MAP_FILES = {"nzp/maps/" + m + ext for m in MAP_NAMES
             for ext in (".bsp", ".nsz", ".txt")}
EXTRA_SUFFIXES = {".bsp", ".nsz", ".txt", ".lit", ".ent", ".loc", ".lmp"}

def once(s, old, new, label):
    n=s.count(old)
    if n != 1:
        raise SystemExit(f"Dual-map menu {label}: expected exactly one anchor, got {n}")
    return s.replace(old,new,1)

def replace_function(s, signature, replacement):
    start=s.find(signature)
    if start<0:
        raise SystemExit("Missing original native Vril menu function: "+signature)
    open_brace=s.find("{",start+len(signature))
    depth=0
    for i in range(open_brace,len(s)):
        if s[i]=="{": depth+=1
        if s[i]=="}":
            depth-=1
            if depth==0: return s[:start]+replacement+s[i+1:]
    raise SystemExit("Unbalanced braces for "+signature)

def menus(root):
    folder=root/"deps/vril/source/menu"
    helper=folder/"menu_helper.c"
    s=helper.read_text(encoding="utf8")
    s=once(s,
        "num_stock_maps = sizeof(stock_maps)/sizeof(stock_maps[0]);",
        'num_stock_maps = 2;\n'
        '\tstock_maps[0].bsp_name = "sanctum_harness";\n'
        '\tstock_maps[0].category = MAP_CATEGORY_USER;\n'
        '\tstock_maps[1].bsp_name = "xziel_proto";\n'
        '\tstock_maps[1].category = MAP_CATEGORY_USER;',
        "exact 2 stock maps")
    helper.write_text(s,encoding="utf8")

    stock=folder/"menu_stockmaps.c"
    s=stock.read_text(encoding="utf8")
    body="""void Menu_StockMaps_Draw (void)
{
    Menu_DrawCustomBackground(true);
    Menu_DrawTitle("XZIEL: CHOOSE MAP", MENU_COLOR_WHITE);
    Menu_DrawMapPanel();
    Menu_DrawMapButton(1, 0, -1, stock_maps[0].category,
        stock_maps[0].bsp_name, Menu_StockMaps_SetMap);
    Menu_DrawMapButton(2, 1, -1, stock_maps[1].category,
        stock_maps[1].bsp_name, Menu_StockMaps_SetMap);
    Menu_DrawButton(-1, 2, "BACK", "Return to XZIEL.", Menu_StockMaps_SetMainMenu);
}"""
    s=replace_function(s,"void Menu_StockMaps_Draw (void)",body)
    stock.write_text(s,encoding="utf8")

    main=folder/"menu_main.c"
    s=main.read_text(encoding="utf8")
    insert="""
/* Two launch choices through original v0.26 map -> PRE-GAME -> START GAME
 * flow; gameplay, pause menu, touch engine and online policy unchanged. */
static void Xziel_QuickSanctum(void)
{
    menu_is_solo = true;
    Map_SetDefaultValues();
    current_selected_bsp = "sanctum_harness";
    Menu_Lobby_Set();
}
static void Xziel_QuickDeadCell(void)
{
    menu_is_solo = true;
    Map_SetDefaultValues();
    current_selected_bsp = "xziel_proto";
    Menu_Lobby_Set();
}
"""
    s=once(s,"void Menu_Main_Draw (void)\n",insert+"\nvoid Menu_Main_Draw (void)\n","main-menu callbacks")
    mainbody="""void Menu_Main_Draw (void)
{
    Menu_DrawCustomBackground(true);
    Menu_DrawTitle("XZIEL ENGINE", MENU_COLOR_WHITE);
    Menu_DrawBuildDate();
    if (!in_submenu) {
        Menu_DrawButton(1, 0, "PLAY: SANCTUM", "Sanctum of Ash - HQ stone church.", Xziel_QuickSanctum);
        Menu_DrawButton(2, 1, "PLAY: DEAD CELL", "Fast zombies combat test arena.", Xziel_QuickDeadCell);
        Menu_DrawDivider(3);
        Menu_DrawButton(3, 2, "CONFIGURATION", "Controls, audio, graphics.", Menu_Configuration_Set);
        Menu_DrawButton(4, 3, "QUIT GAME", "Return to Android.", Menu_EnterSubMenu);
    } else {
        Menu_DrawSubMenu("Quit XZIEL?", "Your progress may not be saved.");
        Menu_DrawButton(1, 0, "QUIT NOW", "", Menu_Quit);
        Menu_DrawButton(2, 1, "KEEP PLAYING", "", Menu_ExitSubMenu);
    }
}"""
    s=replace_function(s,"void Menu_Main_Draw (void)",mainbody)
    main.write_text(s,encoding="utf8")

    pause=(folder/"menu_pause.c").read_text(encoding="utf8")
    assert "XZIEL DEVELOPER" in pause and "XZIEL WEAPON LAB" in pause
    assert "XzielDev_DispatchPendingImpulse" in (root/"deps/vril/source/render/r_hud.c").read_text()
    print("XZIEL_DUAL_MAP_MENU_GREEN main buttons: Sanctum / Dead Cell; Developer untouched")

def archive(root):
    p=root/"android-project/app/src/main/assets/nzp-data.zip"
    fd,tmp=tempfile.mkstemp(prefix="xziel-dual-map-",suffix=".zip",dir=p.parent)
    os.close(fd)
    try:
        with ZipFile(p) as source:
            names=set(source.namelist())
            must=MAP_FILES|{"nzp/progs.dat","nzp/models/xziel/sanctum/sanctum.xzsm"}
            missing=must-names
            if missing:raise SystemExit("Missing dual-map files: "+str(sorted(missing)))
            hq=[n for n in names if n.startswith("nzp/textures/xziel/sanctum/") and n.lower().endswith(".png")]
            if len(hq)<11:raise SystemExit("Sanctum HQ texture atlases missing: "+str(len(hq)))
            from struct import unpack
            magic,version,batches,vertices,indices=unpack("<4sIIII",source.read("nzp/models/xziel/sanctum/sanctum.xzsm")[:20])
            if (magic,version)!=(b"XZSM",2) or vertices<100000:
                raise SystemExit("Sanctum HQ is not original XZSM V2 payload")
            controls={"fire":"fire","aim":"ads","aim_fire":"adsfire",
                      "crouch":"crouch","prone":"prone","slide":"slide",
                      "reload":"reload","knife":"knife","interact":"use",
                      "grenade":"grenade","weapon_swap":"switch",
                      "vault_jump":"jump"}
            for src,dst in controls.items():
                original=Path(f"assets/xziel/official_touch_skins_v1/{src}.png").read_bytes()
                if source.read(f"nzp/gfx/xziel/{dst}.png")!=original:
                    raise SystemExit("Changed verified touch skin: "+src)
            if len(source.read("nzp/progs.dat"))<=50000:
                raise SystemExit("Missing original complete weapons/QuakeC runtime")
            with ZipFile(tmp,"w",allowZip64=True) as dest:
                removed=0
                for entry in source.infolist():
                    n=entry.filename
                    if n.startswith("nzp/maps/") and n!="nzp/maps/":
                        keep=any(n.startswith("nzp/maps/"+m+".") for m in MAP_NAMES) and Path(n).suffix.lower() in EXTRA_SUFFIXES
                        if not keep:
                            removed+=1
                            continue
                    if entry.is_dir():dest.writestr(entry,b"")
                    else:
                        with source.open(entry,"r") as a,dest.open(entry,"w") as b:
                            shutil.copyfileobj(a,b,length=1024*1024)
        with ZipFile(tmp) as z:
            bad=z.testzip()
            if bad:raise SystemExit("Archive CRC error: "+bad)
            maps=sorted(n for n in z.namelist() if n.startswith("nzp/maps/") and n.lower().endswith(".bsp"))
            if maps != ["nzp/maps/sanctum_harness.bsp","nzp/maps/xziel_proto.bsp"]:
                raise SystemExit("Map selector/payload disagree: "+repr(maps))
        os.replace(tmp,p)
        checksum=hashlib.sha256()
        with p.open("rb") as f:
            for block in iter(lambda:f.read(1024*1024),b""):
                checksum.update(block)
        (p.parent/"nzp-data.version").write_text(checksum.hexdigest()+"\n",encoding="ascii")
        print(f"XZIEL_DUAL_MAP_PACKAGE_GREEN removed_map_files={removed} retained_bsp=2 hq_atlases={len(hq)} total_bytes={p.stat().st_size}")
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: slim_v026_sanctum_deadcell.py <build-root>")
    root=Path(sys.argv[1])
    menus(root)
    archive(root)

if __name__=="__main__":main()
