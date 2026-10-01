import bpy
import json
import os
import math
from collections import defaultdict
from pathlib import Path

OUT=Path(os.environ.get("SANCTUM_V2_UV_AUDIT_OUT","sanctum-v2-uv-audit"))
OUT.mkdir(parents=True,exist_ok=True)
TARGET="Catehdral"

obj=bpy.data.objects.get(TARGET)
if obj is None:
    raise SystemExit(f"Missing {TARGET!r}")

deps=bpy.context.evaluated_depsgraph_get()
ev=obj.evaluated_get(deps)
mesh=ev.to_mesh()

def tri_area(a,b,c):
    return abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))*0.5

def audit_layer(layer, mats):
    uvdata=layer.data
    per=defaultdict(lambda:{
        "polygons":0,
        "mesh_area":0.0,
        "uv_area":0.0,
        "degenerate_uv_polygons":0,
        "tiny_uv_polygons":0,
        "extreme_density_polygons":0,
        "density_samples":[],
    })

    for poly in mesh.polygons:
        idx=int(poly.material_index)
        mat=mats[idx].name if idx < len(mats) and mats[idx] else "<None>"
        rec=per[mat]
        rec["polygons"]+=1
        ma=float(poly.area)
        rec["mesh_area"]+=ma

        loops=list(poly.loop_indices)
        if len(loops)<3:
            rec["degenerate_uv_polygons"]+=1
            continue

        uvs=[uvdata[i].uv.copy() for i in loops]
        ua=0.0
        for i in range(1,len(uvs)-1):
            ua+=tri_area(uvs[0],uvs[i],uvs[i+1])
        rec["uv_area"]+=ua

        if ua <= 1e-12:
            rec["degenerate_uv_polygons"]+=1
        elif ua < 1e-8:
            rec["tiny_uv_polygons"]+=1

        if ma>1e-12 and ua>1e-12:
            density=math.sqrt(ua/ma)
            rec["density_samples"].append(density)
            if density>1000.0 or density<1e-6:
                rec["extreme_density_polygons"]+=1

    rows=[]
    for mat,rec in per.items():
        ds=sorted(rec.pop("density_samples"))
        n=len(ds)
        rec["material_name"]=mat
        rec["degenerate_fraction"]=rec["degenerate_uv_polygons"]/rec["polygons"] if rec["polygons"] else 0.0
        rec["tiny_fraction"]=rec["tiny_uv_polygons"]/rec["polygons"] if rec["polygons"] else 0.0
        rec["uv_density_median"]=ds[n//2] if n else None
        rec["uv_density_p05"]=ds[max(0,int(n*0.05)-1)] if n else None
        rec["uv_density_p95"]=ds[min(n-1,int(n*0.95))] if n else None
        rows.append(rec)
    rows.sort(key=lambda r:r["mesh_area"],reverse=True)
    return rows

try:
    if not mesh.uv_layers:
        raise SystemExit("No UV layers on evaluated mesh")

    mats=list(mesh.materials)
    active=mesh.uv_layers.active
    layers=[]
    for layer in mesh.uv_layers:
        layers.append({
            "name":layer.name,
            "is_active":bool(active and layer.name==active.name),
            "materials":audit_layer(layer,mats),
        })

    report={
        "source_object":obj.name,
        "active_uv_layer":active.name if active else None,
        "uv_layer_count":len(mesh.uv_layers),
        "uv_layer_names":[layer.name for layer in mesh.uv_layers],
        "evaluated_vertices":len(mesh.vertices),
        "evaluated_polygons":len(mesh.polygons),
        "layers":layers,
    }

    (OUT/"cathedral-uv-audit.json").write_text(json.dumps(report,indent=2),encoding="utf-8")

    lines=[
        f"source_object={obj.name}",
        f"active_uv_layer={report['active_uv_layer']}",
        f"uv_layer_count={len(mesh.uv_layers)}",
        f"uv_layer_names={report['uv_layer_names']}",
        f"evaluated_vertices={len(mesh.vertices)}",
        f"evaluated_polygons={len(mesh.polygons)}",
    ]
    for layer in layers:
        lines += ["", f"[UV_LAYER] {layer['name']} active={layer['is_active']}",
                  "material | polys | degenerate | tiny | uv_area | mesh_area | median_density | p05 | p95"]
        for r in layer["materials"]:
            lines.append(
                f"{r['material_name']} | {r['polygons']} | {r['degenerate_fraction']:.6f} | "
                f"{r['tiny_fraction']:.6f} | {r['uv_area']:.8f} | {r['mesh_area']:.8f} | "
                f"{r['uv_density_median']} | {r['uv_density_p05']} | {r['uv_density_p95']}"
            )

    (OUT/"cathedral-uv-audit.txt").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("SANCTUM_V2_UV_AUDIT_OK")
    print("\n".join(lines))
finally:
    ev.to_mesh_clear()
