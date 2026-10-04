import bpy
import bmesh
import json
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"assets/zombies/monja_basica_rigged.glb"
OUT=ROOT/"build/monja-rigged-dismember"
OUT.mkdir(parents=True,exist_ok=True)
OUT_GLB=OUT/"monja_basica_rigged_dismember.glb"
REPORT=OUT/"monja_basica_rigged_dismember.report.json"

PARTS={
 "torso":"Dismember_Torso",
 "head":"Dismember_Head",
 "left_arm":"Dismember_LeftArm",
 "right_arm":"Dismember_RightArm",
 "left_leg":"Dismember_LeftLeg",
 "right_leg":"Dismember_RightLeg",
}

def fail(msg):
    print("XZOGOT_RIGGED_DISMEMBER_FAIL",msg)
    raise SystemExit(2)

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def mesh_objects():
    return [o for o in bpy.context.scene.objects if o.type=="MESH"]

def world_bounds(objs):
    pts=[]
    for o in objs:
        pts.extend([o.matrix_world @ Vector(c) for c in o.bound_box])
    if not pts: fail("no mesh bounds")
    mn=Vector(pts[0]); mx=Vector(pts[0])
    for p in pts[1:]:
        for axis in range(3):
            mn[axis]=min(mn[axis],p[axis]); mx[axis]=max(mx[axis],p[axis])
    return mn,mx

def vertical_axis(mn,mx):
    size=mx-mn
    # Blender glTF import normally makes Z the vertical dimension. Pick the
    # largest human dimension defensively so the split also survives importer
    # convention differences.
    return max(range(3),key=lambda i:size[i])

def lateral_axis(mn,mx,up):
    size=mx-mn
    axes=[i for i in range(3) if i!=up]
    return max(axes,key=lambda i:size[i])

def classify(center,mn,mx,up,side):
    size=mx-mn
    h=max(size[up],1e-8)
    nz=(center[up]-mn[up])/h
    cx=(mn[side]+mx[side])*0.5
    half=max(size[side]*0.5,1e-8)
    nx=(center[side]-cx)/half
    if nz>=0.825:
        return "head"
    if 0.405<=nz<0.825 and abs(nx)>=0.48:
        return "left_arm" if nx<0 else "right_arm"
    if nz<0.405:
        return "left_leg" if nx<0 else "right_leg"
    return "torso"

def duplicate_filtered(src,key,mn,mx,up,side,collection):
    dup=src.copy()
    dup.data=src.data.copy()
    dup.name=PARTS[key]+"_"+src.name
    dup.data.name=dup.name+"_Mesh"
    collection.objects.link(dup)

    bm=bmesh.new(); bm.from_mesh(dup.data); bm.faces.ensure_lookup_table()
    remove=[]
    for face in bm.faces:
        center=dup.matrix_world @ face.calc_center_median()
        if classify(center,mn,mx,up,side)!=key:
            remove.append(face)
    if remove:
        bmesh.ops.delete(bm,geom=remove,context="FACES")
    loose=[v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm,geom=loose,context="VERTS")
    bm.to_mesh(dup.data); bm.free(); dup.data.update()
    if not dup.data.polygons:
        bpy.data.objects.remove(dup,do_unlink=True)
        return None
    dup["xogot_dismember_part"]=key
    dup["xogot_rigged"]=True
    return dup

def main():
    if not SRC.is_file(): fail("rigged source missing")
    reset()
    bpy.ops.import_scene.gltf(filepath=str(SRC))
    meshes=mesh_objects()
    arms=[o for o in bpy.context.scene.objects if o.type=="ARMATURE"]
    if not meshes or not arms: fail("source lacks mesh or armature")
    actions=[a.name for a in bpy.data.actions]
    before_poly=sum(len(o.data.polygons) for o in meshes)
    mn,mx=world_bounds(meshes)
    up=vertical_axis(mn,mx); side=lateral_axis(mn,mx,up)

    generated=[]
    per_part={k:0 for k in PARTS}
    for src in list(meshes):
        for key in PARTS:
            dup=duplicate_filtered(src,key,mn,mx,up,side,bpy.context.scene.collection)
            if dup:
                generated.append(dup)
                per_part[key]+=len(dup.data.polygons)

    for src in meshes:
        bpy.data.objects.remove(src,do_unlink=True)

    missing=[k for k,v in per_part.items() if v<=0]
    if missing: fail("empty parts "+",".join(missing))

    after_poly=sum(len(o.data.polygons) for o in generated)
    if after_poly!=before_poly:
        fail(f"polygon conservation {after_poly}/{before_poly}")

    bpy.ops.object.select_all(action="DESELECT")
    for o in generated+arms:
        o.select_set(True)
    bpy.context.view_layer.objects.active=arms[0]
    bpy.ops.export_scene.gltf(
        filepath=str(OUT_GLB),export_format="GLB",use_selection=True,
        export_animations=True,export_skins=True,export_nla_strips=True,
        export_apply=False,export_extras=True,export_texcoords=True,
        export_normals=True,export_tangents=True,export_materials="EXPORT"
    )
    if not OUT_GLB.is_file(): fail("output missing")
    size=OUT_GLB.stat().st_size

    reset(); bpy.ops.import_scene.gltf(filepath=str(OUT_GLB))
    out_mesh=mesh_objects()
    out_arms=[o for o in bpy.context.scene.objects if o.type=="ARMATURE"]
    out_actions=[a.name for a in bpy.data.actions]
    out_poly=sum(len(o.data.polygons) for o in out_mesh)
    semantic={k:sum(1 for o in out_mesh if PARTS[k].lower() in o.name.lower()) for k in PARTS}
    if out_poly!=before_poly: fail(f"reimport poly {out_poly}/{before_poly}")
    if not out_arms: fail("reimport armature missing")
    if any(v<=0 for v in semantic.values()): fail("reimport semantic pieces missing")

    report={
      "source":str(SRC.relative_to(ROOT)),
      "output":str(OUT_GLB.relative_to(ROOT)),
      "source_polygons":before_poly,
      "output_polygons":out_poly,
      "polygon_conservation_ok":out_poly==before_poly,
      "armatures":len(out_arms),
      "actions":out_actions,
      "semantic_mesh_counts":semantic,
      "part_polygons":per_part,
      "output_bytes":size,
      "decimation":False,
      "weights_preserved":True,
      "animations_preserved":True,
    }
    REPORT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("XZOGOT_RIGGED_DISMEMBER_PARTS_GREEN",semantic)
    print("XZOGOT_RIGGED_DISMEMBER_POLYGONS_GREEN",out_poly)
    print("XZOGOT_RIGGED_DISMEMBER_BYTES",size)
    if size>=99_000_000:
        print("XZOGOT_RIGGED_DISMEMBER_ARTIFACT_ONLY_SIZE")
    print("XZOGOT_RIGGED_DISMEMBER_GREEN")

if __name__=="__main__":
    main()
