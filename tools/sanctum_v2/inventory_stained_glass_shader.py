import bpy
import json
import os
from pathlib import Path

OUT=Path(os.environ.get("SANCTUM_V2_SHADER_INV_OUT","sanctum-v2-shader-inventory"))
LIB=Path(os.environ["SANCTUM_V2_SHADER_LIB"])
TARGET="Crown Glass for windows"
OUT.mkdir(parents=True,exist_ok=True)

with bpy.data.libraries.load(str(LIB), link=False) as (data_from, data_to):
    materials=list(data_from.materials)
    node_groups=list(data_from.node_groups)
    if TARGET not in materials:
        raise SystemExit(f"Missing authored target material {TARGET!r}")
    data_to.materials=[TARGET]

mat=bpy.data.materials.get(TARGET)
if mat is None or not mat.use_nodes or not mat.node_tree:
    raise SystemExit(f"Authored material {TARGET!r} has no node tree")

def socket_value(sock):
    if not hasattr(sock,"default_value"):
        return None
    v=sock.default_value
    if hasattr(v,"__len__") and not isinstance(v,str):
        try:
            return [float(x) for x in v]
        except Exception:
            pass
    try:
        return float(v)
    except Exception:
        return str(v)

nodes=[]
for n in mat.node_tree.nodes:
    nodes.append({
        "name":n.name,
        "label":n.label,
        "type":n.bl_idname,
        "inputs":[
            {
                "name":s.name,
                "identifier":getattr(s,"identifier",""),
                "linked":bool(s.is_linked),
                "default":socket_value(s),
            }
            for s in n.inputs
        ],
        "outputs":[
            {
                "name":s.name,
                "identifier":getattr(s,"identifier",""),
                "linked":bool(s.is_linked),
            }
            for s in n.outputs
        ],
    })

links=[]
for l in mat.node_tree.links:
    links.append({
        "from_node":l.from_node.name,
        "from_socket":l.from_socket.name,
        "to_node":l.to_node.name,
        "to_socket":l.to_socket.name,
    })

report={
    "library":str(LIB),
    "materials":materials,
    "node_groups":node_groups,
    "glass_candidates":[n for n in materials if any(k in n.lower() for k in ("glass","crown","window","transparent"))],
    "selected_material":TARGET,
    "selected_material_nodes":nodes,
    "selected_material_links":links,
}
(OUT/"shader-inventory.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_V2_SHADER_INVENTORY_OK")
print(json.dumps(report,indent=2))
