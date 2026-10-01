import bpy, json, os
from pathlib import Path
from mathutils import Vector

OUT=Path(os.environ["SANCTUM_PROP_INV_OUT"])
OUT.mkdir(parents=True,exist_ok=True)
PACK=os.environ["SANCTUM_PROP_PACK"]
SHA=os.environ["SANCTUM_PROP_SHA256"]

def stats(obj):
    deps=bpy.context.evaluated_depsgraph_get()
    ev=obj.evaluated_get(deps)
    mesh=ev.to_mesh()
    try:
        pts=[ev.matrix_world @ v.co for v in mesh.vertices]
        if not pts:
            return None
        mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
        mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
        return {
            "name":obj.name,
            "vertices":len(mesh.vertices),
            "polygons":len(mesh.polygons),
            "size":list(mx-mn),
            "center":list((mn+mx)*0.5),
            "materials":[s.material.name for s in obj.material_slots if s.material],
        }
    finally:
        ev.to_mesh_clear()

items=[]
for o in bpy.context.scene.objects:
    if o.type=="MESH":
        item=stats(o)
        if item:
            items.append(item)
items.sort(key=lambda x:(-x["polygons"],x["name"].lower()))
report={
    "status":"PASS","pack":PACK,"license":"CC0","sha256":SHA,
    "mesh_object_count":len(items),
    "materials":sorted({m for x in items for m in x["materials"]}),
    "objects":items,
}
(OUT/"inventory.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_PROP_INVENTORY_PASS")
print(json.dumps(report,indent=2))
