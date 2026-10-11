#!/usr/bin/env python3
"""Slim the pinned XZIEL v0.26 Developer APK to ORIGINAL Dead Cell only.

Runs AFTER prepare_android.sh (which recompiles QuakeC and assembles the stock
NZ:P zip) and BEFORE Gradle compiles the native Vril C engine.
All shared weapon models, animations, sounds, touch skins and QuakeC survive.
Only other maps' per-level files under nzp/maps are removed. No originals in
Git history or any existing release are deleted.
"""
from pathlib import Path
from zipfile import ZipFile
import os
import re
import shutil
import sys
import tempfile

MAP = "xziel_proto"
KEEP = ("nzp/maps/" + MAP + ".",)
ALLOWED_SUFFIXES = {".bsp", ".nsz", ".txt", ".lit", ".ent", ".loc", ".lmp"}

def once(text, old, new, description):
    if text.count(old) != 1:
        raise SystemExit(f"v0.26 upstream drift: {description} (found {text.count(old)})")
    return text.replace(old, new, 1)

def replace_function(text, signature, body):
    start = text.find(signature)
    if start == -1:
        raise SystemExit("Missing native Vril menu function: " + signature)
    a = text.find("{", start)
    level = 0
    for i in range(a, len(text)):
        if text[i] == "{":
            level += 1
        if text[i] == "}":
            level -= 1
            if level == 0:
                return text[:start] + body + text[i + 1:]
    raise SystemExit("Unbalanced native function " + signature)

def patch_native_menus(deps):
    directory = deps / "vril/source/menu"
    helper = directory / "menu_helper.c"
    s = helper.read_text(encoding="utf-8")
    s = once(s, "num_stock_maps = sizeof(stock_maps)/sizeof(stock_maps[0]);",
        'num_stock_maps = 1;\n\tstock_maps[0].bsp_name = "xziel_proto";\n'
        '\tstock_maps[0].category = MAP_CATEGORY_USER;',
        "single stock map registry")
    helper.write_text(s, encoding="utf-8")

    # Keep v0.26's MAIN MENU untouched. SOLO -> SELECT MAP has one entry.
    # No USER MAPS, RANDOM, other map buttons or dead-end list.
    path = directory / "menu_stockmaps.c"
    s = path.read_text(encoding="utf-8")
    body = """void Menu_StockMaps_Draw (void)
{
    Menu_DrawCustomBackground(true);
    Menu_DrawTitle("SELECT MAP: SOLO", MENU_COLOR_WHITE);
    Menu_DrawMapPanel();
    Menu_DrawMapButton(1, 0, -1, stock_maps[0].category,
        stock_maps[0].bsp_name, Menu_StockMaps_SetMap);
    Menu_DrawButton(-1, 1, "BACK", "Return to Main Menu.",
        Menu_StockMaps_SetMainMenu);
}"""
    s = replace_function(s, "void Menu_StockMaps_Draw (void)", body)
    path.write_text(s, encoding="utf-8")
    assert "XZIEL DEVELOPER" in (directory / "menu_pause.c").read_text()
    print("PASS: original v0.26 main menu + solo list with only Dead Cell; Developer preserved")

def prune_zip(archive):
    archive = Path(archive)
    if not archive.is_file():
        raise SystemExit("Missing NZ:P payload zip: " + str(archive))
    fd, temporary = tempfile.mkstemp(prefix="deadcell-only-", suffix=".zip", dir=archive.parent)
    os.close(fd)
    removed, saved_uncompressed = [], 0
    try:
        with ZipFile(archive, "r") as original:
            names = original.namelist()
            must_keep = {"nzp/maps/xziel_proto.bsp", "nzp/maps/xziel_proto.nsz",
                         "nzp/maps/xziel_proto.txt", "nzp/progs.dat"}
            if not must_keep.issubset(names):
                raise SystemExit("Missing original Dead Cell/QuakeC input: " + str(must_keep - set(names)))
            for path in ("nzp/models/weapons/mp40/v_mp40.mdl",
                         "nzp/models/weapons/mp40/g_mp40.mdl",
                         "nzp/gfx/xziel/fire.png",
                         "nzp/gfx/xziel/ads.png"):
                if path not in names:
                    raise SystemExit("Protected weapon/touch asset missing: " + path)
            with ZipFile(temporary, "w", allowZip64=True) as output:
                for entry in original.infolist():
                    name = entry.filename
                    is_other_map = name.startswith("nzp/maps/") and (
                        # Allow only the original Dead Cell BSP, NSZ, metadata and
                        # its optional strictly named companion files.
                        name != "nzp/maps/" and not (
                            name.startswith(KEEP) and
                            Path(name).suffix.lower() in ALLOWED_SUFFIXES
                        )
                    )
                    if is_other_map:
                        removed.append(name)
                        saved_uncompressed += entry.file_size
                        continue
                    # Stream large shared assets without loading entire zip in RAM.
                    if entry.is_dir():
                        output.writestr(entry, b"")
                    else:
                        with original.open(entry, "r") as source, output.open(entry, "w") as target:
                            shutil.copyfileobj(source, target, length=1024 * 1024)
        with ZipFile(temporary) as packed:
            bad = packed.testzip()
            if bad:
                raise SystemExit("CRC failure in compact payload: " + bad)
            bsps = sorted(n for n in packed.namelist() if
                n.startswith("nzp/maps/") and n.lower().endswith(".bsp"))
            if bsps != ["nzp/maps/xziel_proto.bsp"]:
                raise SystemExit("Other BSPs remained: " + repr(bsps))
            if packed.read("nzp/maps/xziel_proto.bsp") != original_map:
                raise SystemExit("Dead Cell BSP altered by repack")
        original_size = archive.stat().st_size
        os.replace(temporary, archive)
        print(f"PASS: Dead Cell only; removed {len(removed)} other map resources "
              f"({saved_uncompressed:,} uncompressed bytes); zip "
              f"{original_size:,} -> {archive.stat().st_size:,} bytes")
        print("Removed map paths: " + ", ".join(removed[:15]))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: slim_v026_deadcell_only.py <build-root>")
    root = Path(sys.argv[1])
    zip_path = root / "android-project/app/src/main/assets/nzp-data.zip"
    global original_map
    with ZipFile(zip_path) as z:
        original_map = z.read("nzp/maps/xziel_proto.bsp")
    patch_native_menus(root / "deps")
    prune_zip(zip_path)
    import hashlib
    checksum = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (zip_path.parent / "nzp-data.version").write_text(checksum + "\n")
    print("PASS: updated NZ:P payload version checksum " + checksum[:16])

if __name__ == "__main__":
    main()
