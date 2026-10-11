#!/usr/bin/env python3
"""Ship only Dead Cell and Sanctum V2.

Applied AFTER the existing 3-map bridge. Removes old St Giles, not merely hides
it. Preserves the entire QuakeC/Developer/PNG mobile control package. Also fixes
the second issue reported on-device: the inherited HQ renderer desaturated and
clamped ALL source vertex colors, making COLOR_0 ineffective on Sanctum V2.
"""
from pathlib import Path
from zipfile import ZipFile
import hashlib
import os
import re
import shutil
import sys
import tempfile

def once(text, old, new, name):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{name}: expected 1 anchor; got {count}')
    return text.replace(old,new,1)

def menus(base):
    m=base/"deps/vril/source/menu"
    p=m/"menu_main.c";s=p.read_text(encoding="utf8")
    obsolete="""static void Xziel_QuickSanctum(void)
{
    menu_is_solo = true;
    Map_SetDefaultValues();
    current_selected_bsp = "sanctum_harness";
    Menu_Lobby_Set();
}
"""
    s=once(s,obsolete,"","remove obsolete launch callback")
    s=once(s,
      'Menu_DrawButton(1, 0, "PLAY: SANCTUM", "Sanctum of Ash - HQ stone church.", Xziel_QuickSanctum);',
      'Menu_DrawButton(1, 0, "PLAY: SANCTUM V2", "Three-floor church, gallery, undercroft.", Xziel_QuickVertical);',
      'replace first selection')
    s=once(s,
      '        Menu_DrawButton(3, 2, "PLAY: SANCTUM V2", "Oct 2 - three floors, ramps, undercroft.", Xziel_QuickVertical);\n',
      '', 'remove duplicate V2')
    s=once(s,'Menu_DrawDivider(4);','Menu_DrawDivider(3);','separator')
    s=once(s,'Menu_DrawButton(4, 3, "CONFIGURATION"','Menu_DrawButton(3, 2, "CONFIGURATION"','configuration')
    s=once(s,'Menu_DrawButton(5, 4, "QUIT GAME"','Menu_DrawButton(4, 3, "QUIT GAME"','quit')
    assert "PLAY: DEAD CELL" in s and s.count('PLAY: SANCTUM V2')==1
    assert 'sanctum_harness' not in s
    p.write_text(s,encoding="utf8")

    p=m/"menu_helper.c";s=p.read_text(encoding="utf8")
    s=once(s,'num_stock_maps = 3;', 'num_stock_maps = 2;', 'stock map count')
    s=once(s,'stock_maps[0].bsp_name = "sanctum_harness";','stock_maps[0].bsp_name = "sanctum_vertical";','stock 0')
    s=once(s,
      '\tstock_maps[2].bsp_name = "sanctum_vertical";\n\tstock_maps[2].category = MAP_CATEGORY_USER;',
      '', 'third stock removed')
    assert 'sanctum_harness' not in s
    p.write_text(s,encoding='utf8')

    p=m/"menu_stockmaps.c";s=p.read_text(encoding="utf8")
    s=once(s,
       '    Menu_DrawMapButton(3, 2, -1, stock_maps[2].category,\n'
       '        stock_maps[2].bsp_name, Menu_StockMaps_SetMap);\n',
       '', 'third map button')
    s=once(s,
       '    Menu_DrawButton(-1, 3, "BACK", "Return to XZIEL.", Menu_StockMaps_SetMainMenu);',
       '    Menu_DrawButton(-1, 2, "BACK", "Return to XZIEL.", Menu_StockMaps_SetMainMenu);',
       'back')
    p.write_text(s,encoding="utf8")
    assert "XZIEL DEVELOPER" in (m/"menu_pause.c").read_text()
    print("XZIEL_V026_TWO_MAP_MENU_GREEN")

def renderer(base):
    p=base/"deps/vril/source/platform/sdl/gl/gl_xziel_staticmesh.c"
    s=p.read_text(encoding="utf8")
    s=once(s,
       '    if (strstr(cl.worldmodel->name,"sanctum_harness")) return 1;\n',
       '', 'old church renderer dispatch')
    s=once(s,
       'file_len = COM_FOpenFile(xzsm_map_kind == 2 ?\n'
       '        "models/xziel/sanctum_vertical/vertical.xzsm" :\n'
       '        "models/xziel/sanctum/sanctum.xzsm", &f);',
       'file_len = COM_FOpenFile("models/xziel/sanctum_vertical/vertical.xzsm", &f);',
       'single vertical model path')
    s=once(s,
       'Con_Printf(xzsm_map_kind == 2 ?\n'
       '        "XZSM: Vertical V2 mesh loaded batches=%u verts=%u indices=%u bytes=%d\\n" :\n'
       '        "XZSM: Sanctum loaded batches=%u verts=%u indices=%u bytes=%d\\n",',
       'Con_Printf("XZSM: Vertical V2 mesh loaded batches=%u verts=%u indices=%u bytes=%d\\n",',
       'single model log')
    # The inherited St Giles HQ patch converted all RGB to luma and clamped
    # every channel to >=144 during load. That destroys colored per-vertex
    # material data exported in glTF COLOR_0. Color RGBA is already validated
    # by the XZSM v2 batch stride: keep the source untouched for V2.
    match=re.search(r'\s*/\* XZSM v2 baked vertex lighting: clamp the floor.*?'
      r'\n        for \(j = 0; j < b->vertex_count; \+\+j\) \{.*?'
      r'\n        \}\n\n(?=        b->texture = Image_LoadImage\()',s,re.S)
    if match is None:raise RuntimeError("Expected inherited RGB-to-luma vertex clamp not found")
    s=s[:match.start()]+"\n        /* Preserve original Sanctum V2 GLB RGBA vertex colors. */\n\n"+s[match.end():]
    assert "XZSM: Vertical V2 mesh loaded" in s
    assert 'sanctum/sanctum.xzsm' not in s
    p.write_text(s,encoding='utf8')
    print('XZIEL_SANCTUM_V2_COLOR_0_PRESERVED_GREEN')

def trim(base):
    path=base/"android-project/app/src/main/assets/nzp-data.zip"
    fd,tmp=tempfile.mkstemp(prefix="xziel-v2-only-",suffix=".zip",dir=path.parent)
    os.close(fd)
    deleted=0
    try:
        with ZipFile(path) as source,ZipFile(tmp,"w",allowZip64=True) as output:
            for member in source.infolist():
                name=member.filename
                if (name.startswith("nzp/maps/sanctum_harness.") or
                    name.startswith("nzp/models/xziel/sanctum/") or
                    name.startswith("nzp/textures/xziel/sanctum/")):
                    deleted+=1
                    continue
                if member.is_dir():
                    output.writestr(member,b"")
                else:
                    with source.open(member) as a,output.open(member,"w") as b:
                        shutil.copyfileobj(a,b,length=1024*1024)
        with ZipFile(tmp) as z:
            assert z.testzip() is None
            names=set(z.namelist())
            bsp=sorted(n for n in names if n.startswith("nzp/maps/") and n.endswith(".bsp"))
            assert bsp==["nzp/maps/sanctum_vertical.bsp","nzp/maps/xziel_proto.bsp"],bsp
            assert not any('sanctum_harness' in n or n.startswith("nzp/models/xziel/sanctum/")
                 or n.startswith("nzp/textures/xziel/sanctum/") for n in names)
            assert "nzp/models/xziel/sanctum_vertical/vertical.xzsm" in names
            assert len([n for n in names if n.startswith("nzp/textures/xziel/sanctum_vertical/") and n.endswith(".png")])>=20
            assert len(z.read("nzp/progs.dat"))>50000
            for pic in ("fire","ads","adsfire","reload","slide","jump","crouch","prone","knife","use","grenade","switch"):
                assert "nzp/gfx/xziel/"+pic+".png" in names
        os.replace(tmp,path)
        h=hashlib.sha256()
        with path.open("rb") as f:
            for part in iter(lambda:f.read(1024*1024),b""):h.update(part)
        (path.parent/"nzp-data.version").write_text(h.hexdigest()+"\n")
        print("XZIEL_DEADCELL_PLUS_SANCTUM_V2_ONLY_GREEN removed_st_giles_files",deleted,
              "bytes",path.stat().st_size)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def main():
    if len(sys.argv)!=2:raise SystemExit("usage: finish_two_map_vertical.py <build>")
    base=Path(sys.argv[1])
    menus(base)
    renderer(base)
    trim(base)
if __name__=="__main__":main()
