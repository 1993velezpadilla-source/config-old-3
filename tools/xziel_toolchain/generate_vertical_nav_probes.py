#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

def gltf_point(blender_xyz):
    # Blender Z-up -> exported glTF Y-up, matching trimesh runtime extraction.
    x, y, z = blender_xyz
    return [x, z, -y]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--report",required=True)
    ap.add_argument("--out",required=True)
    ap.add_argument("--json",dest="json_out")
    args=ap.parse_args()

    d=json.loads(Path(args.report).read_text(encoding="utf-8"))
    floors=d["floor_heights_m"]
    main_min,main_max=d["main_floor_bounds"]
    under_min,under_max=d["undercroft_bounds"]
    gallery=d["gallery"]
    openings=d["floor_openings"]

    nave_z=float(floors["nave"])
    lower_z=float(floors["undercroft"])
    upper_z=float(floors["gallery"])
    cx=(float(main_min[0])+float(main_max[0]))*0.5

    east=openings["east"]
    east_x=(float(east[0])+float(east[1]))*0.5
    east_y0=float(east[2])
    east_y1=float(east[3])

    # Route deliberately follows the east undercroft shortcut and east upper
    # ramp so all three authored gameplay levels must belong to one Detour
    # component. Points sit on flat floor plates, not on the ramps themselves.
    probes=[
        {
            "name":"undercroft_east",
            "blender":[east_x, min(east_y1-0.65,float(under_max[1])-0.65), lower_z+0.08],
        },
        {
            "name":"nave_east_shortcut",
            "blender":[east_x, east_y0-0.85, nave_z+0.08],
        },
        {
            "name":"nave_upper_east_base",
            "blender":[cx+float(gallery["x_offset"]), min(float(main_max[1])-0.8,float(gallery["y1"])+5.7), nave_z+0.08],
        },
        {
            "name":"gallery_east",
            "blender":[cx+float(gallery["x_offset"]), float(gallery["y1"])-1.0, upper_z+0.08],
        },
    ]

    for p in probes:
        p["gltf"]=gltf_point(p["blender"])

    out=Path(args.out)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(
        "\n".join(
            f'{p["name"]} {p["gltf"][0]:.6f} {p["gltf"][1]:.6f} {p["gltf"][2]:.6f}'
            for p in probes
        )+"\n",
        encoding="utf-8",
    )

    if args.json_out:
        Path(args.json_out).write_text(json.dumps({
            "status":"PASS",
            "source_report":str(args.report),
            "axis_conversion":"Blender (X,Y,Z) -> glTF/Detour (X,Z,-Y)",
            "probes":probes,
        },indent=2),encoding="utf-8")

    print("XZIEL_VERTICAL_NAV_PROBES_READY")
    for p in probes:
        print(p["name"],"BLENDER",p["blender"],"GLTF",p["gltf"])

if __name__=="__main__":
    main()
