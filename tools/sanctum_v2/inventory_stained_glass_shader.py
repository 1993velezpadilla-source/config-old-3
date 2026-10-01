import bpy
import json
import os
from pathlib import Path

OUT=Path(os.environ.get("SANCTUM_V2_SHADER_INV_OUT","sanctum-v2-shader-inventory"))
LIB=Path(os.environ["SANCTUM_V2_SHADER_LIB"])
OUT.mkdir(parents=True,exist_ok=True)

with bpy.data.libraries.load(str(LIB), link=False) as (data_from, data_to):
    materials=list(data_from.materials)
    node_groups=list(data_from.node_groups)

report={
    "library":str(LIB),
    "materials":materials,
    "node_groups":node_groups,
    "glass_candidates":[n for n in materials if any(k in n.lower() for k in ("glass","crown","window","transparent"))],
}
(OUT/"shader-inventory.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_V2_SHADER_INVENTORY_OK")
print(json.dumps(report,indent=2))
