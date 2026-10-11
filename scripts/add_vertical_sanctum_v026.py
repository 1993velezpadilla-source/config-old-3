#!/usr/bin/env python3
"""Extend *verified* dual-map v0.26, never modify prior working release.

Adds the Oct-02 original Sanctum V2 Vertical GLB visual data and a distinct
third map. The advanced native Vulkan GLB/navbin/hull format is not directly
runnable by Vril: build_vril_vertical_map.py produces explicit XZSM+BSP
adapters and reports limited collision fidelity.
"""
import hashlib
from pathlib import Path
from zipfile import ZipFile
import re
import os
import shutil
import sys
import tempfile

def replace_once(s,old,new,desc):
    n=s.count(old)
    if n!=1:raise SystemExit(f"Vertical map {desc}: expected 1 anchor got {n}")
    return s.replace(old,new,1)

def patch_menu(root):
    m=root/"deps/vril/source/menu"
    p=m/"menu_helper.c"
    s=p.read_text()
    s=replace_once(s,'num_stock_maps = 2;','num_stock_maps = 3;','map count')
    s=replace_once(s,'stock_maps[1].category = MAP_CATEGORY_USER;',
      'stock_maps[1].category = MAP_CATEGORY_USER;\n'
      '\tstock_maps[2].bsp_name = "sanctum_vertical";\n'
      '\tstock_maps[2].category = MAP_CATEGORY_USER;', 'third registry')
    p.write_text(s)
    p=m/"menu_main.c"
    s=p.read_text()
    s=replace_once(s,'static void Xziel_QuickDeadCell(void)\n',
      'static void Xziel_QuickVertical(void)\n'
      '{\n    menu_is_solo = true;\n    Map_SetDefaultValues();\n'
      '    current_selected_bsp = "sanctum_vertical";\n    Menu_Lobby_Set();\n}\n'
      'static void Xziel_QuickDeadCell(void)\n', 'vertical direct launch')
    s=replace_once(s,
      'Menu_DrawButton(2, 1, "PLAY: DEAD CELL", "Fast zombies combat test arena.", Xziel_QuickDeadCell);',
      'Menu_DrawButton(2, 1, "PLAY: DEAD CELL", "Fast zombies combat test arena.", Xziel_QuickDeadCell);\n'
      '        Menu_DrawButton(3, 2, "PLAY: SANCTUM V2", "Oct 2 - three floors, ramps, undercroft.", Xziel_QuickVertical);',
      'new main menu button')
    s=replace_once(s,'Menu_DrawDivider(3);','Menu_DrawDivider(4);','separator')
    s=replace_once(s,'Menu_DrawButton(3, 2, "CONFIGURATION"', 'Menu_DrawButton(4, 3, "CONFIGURATION"','config')
    s=replace_once(s,'Menu_DrawButton(4, 3, "QUIT GAME"', 'Menu_DrawButton(5, 4, "QUIT GAME"','quit')
    p.write_text(s)

    p=m/"menu_stockmaps.c"
    s=p.read_text()
    s=replace_once(s,
      '    Menu_DrawButton(-1, 2, "BACK", "Return to XZIEL.", Menu_StockMaps_SetMainMenu);',
      '    Menu_DrawMapButton(3, 2, -1, stock_maps[2].category,\n'
      '        stock_maps[2].bsp_name, Menu_StockMaps_SetMap);\n'
      '    Menu_DrawButton(-1, 3, "BACK", "Return to XZIEL.", Menu_StockMaps_SetMainMenu);',
      '3-map stock selector')
    p.write_text(s)
    assert 'XZIEL DEVELOPER' in (m/'menu_pause.c').read_text()
    assert 'PLAY: SANCTUM V2' in s or 'PLAY: SANCTUM V2' in (m/'menu_main.c').read_text()
    print('VERTICAL_SANCTUM_THREE_MAP_MENU_GREEN')

def patch_renderer(root):
    p=root/"deps/vril/source/platform/sdl/gl/gl_xziel_staticmesh.c"
    s=p.read_text()
    s=replace_once(s,'static qboolean xzsm_authority_reported = false;',
      'static qboolean xzsm_authority_reported = false;\n'
      'static int xzsm_map_kind = 0;', 'map state')
    s=replace_once(s,
      'static qboolean XZSM_IsSanctum(void)\n{\n'
      '    if (!cl.worldmodel || !cl.worldmodel->name[0])\n'
      '        return false;\n'
      '    return strstr(cl.worldmodel->name, "sanctum_harness") != NULL;\n}\n',
      'static int XZSM_DesiredMap(void)\n{\n'
      '    if (!cl.worldmodel || !cl.worldmodel->name[0]) return 0;\n'
      '    if (strstr(cl.worldmodel->name,"sanctum_harness")) return 1;\n'
      '    if (strstr(cl.worldmodel->name,"sanctum_vertical")) return 2;\n'
      '    return 0;\n}\n', 'select correct mesh')
    s=replace_once(s,
      'file_len = COM_FOpenFile("models/xziel/sanctum/sanctum.xzsm", &f);',
      'file_len = COM_FOpenFile(xzsm_map_kind == 2 ?\n'
      '        "models/xziel/sanctum_vertical/vertical.xzsm" :\n'
      '        "models/xziel/sanctum/sanctum.xzsm", &f);','load chosen model')
    s=replace_once(s,
      '    if (!XZSM_IsSanctum()) {\n'
      '        if (xzsm_loaded || xzsm_attempted)\n'
      '            XZSM_Free();\n'
      '        return false;\n'
      '    }\n',
      '    int wanted = XZSM_DesiredMap();\n'
      '    if (wanted != xzsm_map_kind) {\n'
      '        XZSM_Free();\n'
      '        xzsm_map_kind = wanted;\n'
      '    }\n'
      '    if (!wanted) return false;\n',
      'reset mesh on map transition')
    s=replace_once(s,
      'Con_Printf("XZSM: Sanctum loaded batches=%u verts=%u indices=%u bytes=%d\\n",',
      'Con_Printf(xzsm_map_kind == 2 ?\n'
      '        "XZSM: Vertical V2 mesh loaded batches=%u verts=%u indices=%u bytes=%d\\n" :\n'
      '        "XZSM: Sanctum loaded batches=%u verts=%u indices=%u bytes=%d\\n",',
      'report correct render target')
    p.write_text(s)
    print('VERTICAL_SANCTUM_XZSM_DISPATCH_GREEN')

def package(root,assets):
    a=root/"android-project/app/src/main/assets/nzp-data.zip"
    root=Path(assets)
    paths=list((root/"nzp").rglob("*"))
    files={str(f.relative_to(root)).replace("\\","/"):f for f in paths if f.is_file()}
    important={'nzp/maps/sanctum_vertical.bsp','nzp/maps/sanctum_vertical.nsz',
               'nzp/maps/sanctum_vertical.txt',
               'nzp/models/xziel/sanctum_vertical/vertical.xzsm'}
    assert not(important-set(files)), sorted(important-set(files))
    if len([x for x in files if x.startswith('nzp/textures/xziel/sanctum_vertical/') and x.endswith('.png')])<20:
        raise SystemExit('Sanctum Vertical material textures lost')
    fd,tmp=tempfile.mkstemp(prefix='three-maps-',suffix='.zip',dir=a.parent)
    os.close(fd)
    try:
        with ZipFile(a) as old, ZipFile(tmp,'w',allowZip64=True) as new:
            allnames=set(old.namelist())
            if allnames & set(files):
                raise SystemExit('Preview bundle would overwrite baseline paths: '+str(sorted(allnames & set(files))[:5]))
            for member in old.infolist():
                if member.is_dir():new.writestr(member,b'')
                else:
                    with old.open(member) as source,new.open(member,'w') as target:
                        shutil.copyfileobj(source,target,1024*1024)
            for path,file in sorted(files.items()):
                with file.open('rb') as src,new.open(path,'w') as dst:
                    shutil.copyfileobj(src,dst,1024*1024)
        with ZipFile(tmp) as z:
            if z.testzip():raise SystemExit('CRC failure in new package')
            maps=sorted(n for n in z.namelist() if n.startswith('nzp/maps/') and n.endswith('.bsp'))
            assert maps==['nzp/maps/sanctum_harness.bsp','nzp/maps/sanctum_vertical.bsp','nzp/maps/xziel_proto.bsp'],maps
            assert len(z.read('nzp/progs.dat'))>50000
            assert all(x in z.namelist() for x in ('nzp/gfx/xziel/fire.png','nzp/gfx/xziel/reload.png'))
        os.replace(tmp,a)
        h=hashlib.sha256()
        with a.open('rb') as src:
            for b in iter(lambda:src.read(1024*1024),b''):h.update(b)
        (a.parent/'nzp-data.version').write_text(h.hexdigest()+'\n')
        print('VERTICAL_SANCTUM_3_BSP_PLUS_XZSM_GREEN',a.stat().st_size)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

if __name__=="__main__":
    if len(sys.argv)!=3:raise SystemExit('usage: add_vertical_sanctum_v026.py <build-root> <addon-root>')
    build=Path(sys.argv[1])
    patch_menu(build);patch_renderer(build)
    package(build,Path(sys.argv[2]))
