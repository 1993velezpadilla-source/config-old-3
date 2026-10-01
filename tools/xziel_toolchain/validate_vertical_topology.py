#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

def fail_item(items, code, detail):
    items.append({"code":code,"detail":detail})

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--report",required=True)
    ap.add_argument("--out",required=True)
    args=ap.parse_args()

    d=json.loads(Path(args.report).read_text(encoding="utf-8"))
    errors=[]
    warnings=[]

    main_min,main_max=d["main_floor_bounds"]
    under_min,under_max=d["undercroft_bounds"]
    gallery=d["gallery"]
    openings=d["floor_openings"]

    if float(d.get("vertical_span_m",0)) < 7.0:
        fail_item(errors,"VERTICAL_SPAN","vertical span below 7 m")

    # The current undercroft shell uses continuous perimeter walls. Therefore
    # stair/ramp footprints must land inside that shell instead of crossing a
    # solid perimeter wall. If a future design authors explicit wall portals,
    # this rule can be upgraded to consume those portal rectangles instead.
    ux0,uy0=float(under_min[0]),float(under_min[1])
    ux1,uy1=float(under_max[0]),float(under_max[1])
    margin=0.08
    for name,box in openings.items():
        x0,x1,y0,y1=map(float,box)
        if x0 < ux0-margin or x1 > ux1+margin:
            fail_item(errors,"RAMP_OUTSIDE_UNDERCROFT_X",f"{name}: [{x0},{x1}] outside [{ux0},{ux1}]")
        if y0 < uy0-margin or y1 > uy1+margin:
            fail_item(errors,"RAMP_CROSSES_UNDERCROFT_WALL",f"{name}: [{y0},{y1}] outside [{uy0},{uy1}]")

    # Gallery has to sit safely inside the proven main-floor footprint rather
    # than inside the masonry skin.
    mx0,my0=float(main_min[0]),float(main_min[1])
    mx1,my1=float(main_max[0]),float(main_max[1])
    cx=(mx0+mx1)*0.5
    gx=float(gallery["x_offset"])
    gw=float(gallery["width"])
    gy0=float(gallery["y0"])
    gy1=float(gallery["y1"])
    safety=0.35
    west_outer=cx-gx-gw*0.5
    east_outer=cx+gx+gw*0.5
    if west_outer < mx0+safety or east_outer > mx1-safety:
        fail_item(errors,"GALLERY_TOO_CLOSE_TO_SIDE_WALL",
                  f"gallery outer X [{west_outer},{east_outer}] vs safe [{mx0+safety},{mx1-safety}]")
    if gy0 < my0+safety or gy1 > my1-safety:
        fail_item(errors,"GALLERY_TOO_CLOSE_TO_END_WALL",
                  f"gallery Y [{gy0},{gy1}] vs safe [{my0+safety},{my1-safety}]")

    status="PASS" if not errors else "FAIL"
    result={
        "status":status,
        "source_report":str(args.report),
        "errors":errors,
        "warnings":warnings,
        "checks":{
            "vertical_span_m":d.get("vertical_span_m"),
            "undercroft_bounds":d["undercroft_bounds"],
            "floor_openings":openings,
            "gallery":gallery,
            "main_floor_bounds":d["main_floor_bounds"],
        },
    }
    Path(args.out).write_text(json.dumps(result,indent=2),encoding="utf-8")
    print("XZIEL_VERTICAL_TOPOLOGY_"+status)
    print(json.dumps(result,indent=2))
    if errors:
        raise SystemExit(2)

if __name__=="__main__":
    main()
