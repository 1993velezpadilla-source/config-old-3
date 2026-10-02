import bpy, json, os
from pathlib import Path
from mathutils import Vector
import runpy

OUT=Path(os.environ.get("SANCTUM_GROUP_FIT_OUT","sanctum-group-fit"))
OUT.mkdir(parents=True,exist_ok=True)
profiles=json.loads(Path("docs/sanctum-reference-silhouettes.v1.json").read_text())
fitmod=runpy.run_path("tools/sanctum_v2/reference_group_fit.py")
fit=fitmod["fit_object_group_to_silhouettes"]
check=fitmod["count_group_violations"]

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

def box(name,loc,size):
    bpy.ops.mesh.primitive_cube_add(size=1.0,location=loc)
    o=bpy.context.object
    o.name=name
    o.dimensions=Vector(size)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return o

# Deliberately oversized proxy altar to prove the fitter changes multiple separate objects.
objs=[
    box("TEST_STEP",(0,0,0.15),(5.6,3.2,0.3)),
    box("TEST_BODY",(0,0,0.95),(4.5,1.7,1.5)),
    box("TEST_POST_L",(-2.15,-0.1,1.1),(0.4,1.9,1.8)),
    box("TEST_POST_R",(2.15,-0.1,1.1),(0.4,1.9,1.8)),
]
p=profiles["altar"]
dims={"width":4.90,"depth":2.75,"height":1.84}
stats=fit(objs,p["front_body"]["points"],p["side_left"]["points"],dims,(0.0,0.0),0.0)
audit=check(objs,p["front_body"]["points"],p["side_left"]["points"],dims,(0.0,0.0),0.0)

if audit["violations"]!=0:
    raise SystemExit(f"SANCTUM_GROUP_FIT_FAIL: {audit}")
if stats["changed_vertices"]<=0:
    raise SystemExit(f"SANCTUM_GROUP_FIT_FAIL: no vertices changed {stats}")

for o in bpy.context.selected_objects:
    o.select_set(False)
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active=objs[0]
glb=OUT/"altar-group-fit-test.glb"
bpy.ops.export_scene.gltf(filepath=str(glb),export_format="GLB",use_selection=True,export_apply=True,export_extras=True)

report={"status":"PASS","fit":stats,"audit":audit,"glb":glb.name,"glb_bytes":glb.stat().st_size}
(OUT/"group-fit-report.json").write_text(json.dumps(report,indent=2))
print("SANCTUM_GROUP_SILHOUETTE_FIT_PASS")
print(json.dumps(report,indent=2))
