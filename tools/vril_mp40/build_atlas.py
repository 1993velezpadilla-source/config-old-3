#!/usr/bin/env python3
"""Generate the Vril MDL external skins as a 2-panel color atlas.

MDL palette fallback is intentionally monochrome. OpenGL Vril's gl_model.c
first loads v_mp40.mdl_0.tga or .pcx as an external override.
"""
from pathlib import Path
from PIL import Image
import argparse
import json
import struct

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--gun", type=Path, required=True)
    p.add_argument("--hands", type=Path, required=True)
    p.add_argument("--outdir", type=Path, required=True)
    args = p.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    atlas = Image.new("RGB", (1024, 512))
    for file, x in ((args.gun, 0), (args.hands, 512)):
        if not file.is_file():
            raise FileNotFoundError("Source diffuse texture missing: " + str(file))
        with Image.open(file) as im:
            src = im.convert("RGB").resize((512, 512), Image.Resampling.LANCZOS)
            atlas.paste(src, (x, 0))
    # Named after Vril gl_model.c path: COM_StripExtension + '.mdl_0'
    for index in (0, 1):
        atlas.save(args.outdir / f"v_mp40.mdl_{index}.tga", format="TGA")
    with (args.outdir / "v_mp40.mdl").open("rb") as f:
        data = f.read(84)
    if data[:4] != b"IDPO" or struct.unpack_from("<i", data, 4)[0] != 6:
        raise RuntimeError("Not a Quake MDL version 6")
    nskins, sw, sh, nverts, ntris, nframes = struct.unpack_from("<6i", data, 48)
    if nskins != 2 or (sw, sh) != (256, 128) or nframes != 46:
        raise RuntimeError("Wrong MDL layout: " + repr((nskins, sw, sh, nframes)))
    report = {"atlas": "v_mp40.mdl_0.tga", "variant": "v_mp40.mdl_1.tga",
              "size": list(atlas.size), "png_gun": str(args.gun),
              "png_hands": str(args.hands), "mdl_vertices": nverts,
              "mdl_triangles": ntris, "mdl_frames": nframes,
              "status": "requires actual Android visual approval"}
    (args.outdir / "atlas-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print("VRIL_MP40_TGA_ATLAS_BUILT_2_SOURCES", atlas.size)


if __name__ == "__main__":
    main()
