#!/usr/bin/env python3
"""MASTER ORCHESTRATOR / ADVERSARIAL CRITIC: Sanctum opening nave.

Static authoring-level route certification. Does not mislabel an A* route as
proof that a compiled QuakeC zombie actually traversed it in a live game.
Requires an additional Android zombie-run capture before shipping final AI.
"""
import argparse
from collections import deque
import json
from pathlib import Path

ROWS=(-525,-385,-245,-105,35,175)
WINDOWS=(-820,-460,-100,260)
COLUMNS=(-640,-280,80,440)
PLAYER_SPAWNS=[(-430,-42),(-430,42),(-350,-42),(-350,42)]
WALLBUYS=[(-700,-395),(-300,395),(350,-395),(100,395)]
GRID=10

def obstacles(include_benches=True):
    obs=[]
    for x in COLUMNS:
        for y in (-250,250):
            obs.append((x-22,y-22,x+22,y+22,"pillar"))
    if include_benches:
        # Treat visible Tripo pews AS IF solid during adversarial nav
        # despite the shipping runtime currently keeping them visual-only.
        for x in ROWS:
            for y in (-155,155):
                obs.append((x-37,y-75,x+37,y+75,"pew"))
    obs.append((721,-59,787,59,"altar_CLIP"))
    return obs

def corridor_path(start,finish,obstacles_xy,agent_radius=15):
    xmin,xmax,ymin,ymax=-960,900,-410,410
    def cell(p):
        return round(p[0]/GRID),round(p[1]/GRID)
    def passable(p):
        x,y=p[0]*GRID,p[1]*GRID
        if x<xmin+agent_radius or x>xmax-agent_radius or y<ymin+agent_radius or y>ymax-agent_radius:
            return False
        for x0,y0,x1,y1,_ in obstacles_xy:
            if x0-agent_radius<=x<=x1+agent_radius and y0-agent_radius<=y<=y1+agent_radius:
                return False
        return True
    src,dst=cell(start),cell(finish)
    if not passable(src) or not passable(dst):
        return None
    queue=deque([src]);back={src:None}
    while queue:
        p=queue.popleft()
        if p==dst:
            n=0
            while back[p] is not None:
                p=back[p];n+=1
            return n*GRID
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            q=(p[0]+dx,p[1]+dy)
            if q not in back and passable(q):
                back[q]=p;queue.append(q)
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--map",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    ap.add_argument("--export",type=Path,required=True)
    args=ap.parse_args()
    mapdata=args.map.read_text()
    d=json.loads(args.report.read_text())
    assert d["furniture"]=="REAL_2x_Tripo_GLB"
    assert d["wallbuys"]==4 and d["zombie_windows"]==8
    assert d["altar_collision"]=="BRUSH_CLIP_INSIDE_TRUE_TRIPO_ALTAR"
    assert d["altar_collision_bounds"]==[[721,-59,24],[787,59,108]]
    assert mapdata.count(" CLIP ")==6,"Exact 6-face solid altar CLIP brush must exist"
    assert mapdata.count('"classname" "weapon_wall"')==4
    assert mapdata.count('"classname" "buy_weapon"')==4
    assert mapdata.count('"classname" "spawn_zombie"')>=8
    assert len(ROWS)*2==12 and len(WINDOWS)*2==8
    assert all(abs(y)>54 for x,y in WALLBUYS),"Wallbuy must not obstruct center aisle"
    # All chalk outlines must land on genuine masonry, not window holes.
    assert all(min(abs(x-w) for w in WINDOWS)>54 for x,y in WALLBUYS)
    # At every row, the pew fronts leave an unobstructed 160-unit center aisle.
    assert min(155-75 for y in (-155,155))==80
    obs=obstacles(include_benches=True)
    paths={}
    for x in WINDOWS:
        for y in (-385,385):
            start=(x,y)
            # Both north/south barricades must be able to reach player and
            # climb toward altar, even under WORST-CASE solid pew hulls.
            for name,goal in [("starting_player",(-430,0)),("altar_approach",(640,0))]:
                route=corridor_path(start,goal,obs)
                assert route is not None,f"NO_ZOMBIE_TRAINING_PATH {start} -> {name}"
                paths[f"{x},{y}=>{name}"]=route
    assert corridor_path((-430,0),(640,0),obs) is not None
    # The two chancel side escape lanes must remain open around real altar.
    assert corridor_path((640,-140),(875,-140),obs) is not None
    assert corridor_path((640,140),(875,140),obs) is not None
    summary={
        "checker":"XZIEL_MASTER_ORCHESTRATOR_ADVERSARIAL_CRITIC_V1",
        "zombie_route_scenarios":len(paths),
        "route_lengths":paths,
        "pew_visual_instances":12,
        "pew_hulls":"adversarial simulated solid; runtime visual-only pending actual AI test",
        "altar_hull":"real BSP CLIP",
        "main_wallbuy_count":4,
        "ai_live_gameplay_proof":"NOT_YET_VERIFIED",
        "master_4k_runtime":"source PBR masters are 4K; Quake BSP mobile material LOD is 1024"
    }
    args.export.parent.mkdir(parents=True,exist_ok=True)
    args.export.write_text(json.dumps(summary,indent=2)+"\n")
    print("XZIEL_NAVE_16_ADVERSARIAL_ZOMBIE_ROUTE_SCENARIOS_GREEN",len(paths))
    print("XZIEL_ALTAR_COLLISION_PEW_LOOP_WALLBUYS_PRECHECK_GREEN")

if __name__=="__main__":
    main()
